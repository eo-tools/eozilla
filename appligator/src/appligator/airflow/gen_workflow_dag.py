#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


import inspect
from pathlib import Path
from typing import Annotated, Any, Callable, get_args, get_origin

from procodile import Process
from procodile.workflow import (
    FromMainDependency,
    FromStepDependency,
    FINAL_STEP_ID,
    WorkflowStepRegistry,
)


def gen_workflow_dag(
    dag_id: str,
    registry: WorkflowStepRegistry,
    image: str,
    output_dir: Path,
) -> str:
    """
    Generates a fully-formed Airflow DAG Python file using KubernetesPodOperators
    and the final step using PythonOperator.

    The last `final_step` is a synthetic final step that just passes the xcom from
    the actual last step to its output so that other services can consume the output
    of the dag from a persistent `final_step` task_id.
    """

    if not isinstance(registry, WorkflowStepRegistry):
        raise TypeError(f"unexpected type for registry: {type(registry).__name__}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    steps_dict = registry.steps
    first_step_dict = registry.main

    main_step = next(iter(first_step_dict.values()))
    main_step_id = main_step.description.id
    main_param_meta = extract_param_defaults(main_step.function)

    cmd = render_cmd(
        func_module=main_step.function.__module__,
        func_qualname=main_step.function.__qualname__,
        inputs=_render_main_env(main_param_meta),
        output_keys=_render_outputs(main_step),
    )

    dag_code = f'''\
from datetime import datetime

from airflow import DAG
from airflow.models.param import Param
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import PythonOperator

def _final_step_callable(ti, upstream_task_id):
    return ti.xcom_pull(task_ids=upstream_task_id)

with DAG(
    dag_id="{dag_id}",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    render_template_as_native_obj=True,
    params={{
{_render_params(main_param_meta)}
    }},
    is_paused_upon_creation=False,
) as dag:

    tasks = {{}}

    tasks["{main_step_id}"] = KubernetesPodOperator(
        task_id="{main_step_id}",
        name="{main_step_id.replace("_", "-")}",
        image="{image}",
        cmds=[
            "python", 
            "-c", 
            {cmd!r}
        ],
        do_xcom_push=True,
    )
'''

    for step_id, meta in steps_dict.items():
        if step_id == FINAL_STEP_ID:
            continue

        step = meta["step"]
        deps = meta["dependencies"]

        cmd = render_cmd(
            func_module=step.function.__module__,
            func_qualname=step.function.__qualname__,
            inputs=_render_step_env(step, deps, main_step),
            output_keys=_render_outputs(step),
        )

        dag_code += f'''
    tasks["{step_id}"] = KubernetesPodOperator(
        task_id="{step_id}",
        name="{step_id.replace("_", "-")}",
        image="{image}",
        cmds=[
            "python", 
            "-c", 
            {cmd!r}
        ],
        do_xcom_push=True,
    )
'''

    all_tasks = set(steps_dict.keys()) | {main_step_id}

    upstream_tasks = set()
    for s_id, meta  in steps_dict.items():
        if s_id == FINAL_STEP_ID: continue
        for dep in meta["dependencies"].values():
            if dep["type"] == "from_step":
                upstream_tasks.add(dep["step_id"])
            elif dep["type"] == "from_main":
                upstream_tasks.add(main_step_id)

    leaf_tasks = all_tasks - upstream_tasks

    if len(leaf_tasks) != 1:
        raise ValueError(f"Expected exactly one leaf step, found {leaf_tasks}")

    last_step_id = next(iter(leaf_tasks))

    dag_code += f'''
    tasks["{FINAL_STEP_ID}"] = PythonOperator(
        task_id="{FINAL_STEP_ID}",
        python_callable=_final_step_callable,
        op_kwargs={{
            "upstream_task_id": "{last_step_id}"
        }},
        do_xcom_push=True
    )
    '''

    dag_code += "\n"
    for step_id, meta in steps_dict.items():
        for dep in meta["dependencies"].values():
            if step_id == FINAL_STEP_ID:
                continue
            if dep["type"] == "from_step":
                dag_code += f'    tasks["{dep["step_id"]}"] >> tasks["{step_id}"]\n'
            elif dep["type"] == "from_main":
                dag_code += f'    tasks["{main_step_id}"] >> tasks["{step_id}"]\n'

    dag_code += f'    tasks["{last_step_id}"] >> tasks["{FINAL_STEP_ID}"]\n'

    return dag_code


def extract_param_defaults(
    func: Callable[[Any], Any],
) -> dict[str, dict[str, str | None]]:
    """
    Extract default values and Airflow param types from a function signature.
    """
    sig = inspect.signature(func)
    result = {}

    for name, param in sig.parameters.items():
        default = None
        if param.default is not inspect.Parameter.empty:
            default = param.default

        airflow_type = "string"
        annotation = param.annotation

        if annotation is not inspect.Parameter.empty:
            origin = get_origin(annotation)
            if origin is Annotated:
                base_type = get_args(annotation)[0]
            else:
                base_type = annotation

            if base_type in (int, float):
                airflow_type = "number"
            elif base_type is bool:
                airflow_type = "boolean"

        result[name] = {
            "default": default,
            "type": airflow_type,
        }

    return result


def _render_params(param_meta: dict[str, dict[str, str | None]]) -> str:
    lines = []
    for name, meta in param_meta.items():
        default = meta["default"]
        airflow_type = meta["type"]
        default_repr = "None" if default is None else repr(default)

        lines.append(f'        "{name}": Param({default_repr}, type="{airflow_type}")')

    return ",\n".join(lines)


def _render_main_env(param_meta: dict[str, dict[str, str | None]]) -> str:
    return ",\n".join(
        f'            "{name}": "{{{{ params.{name} }}}}"' for name in param_meta.keys()
    )


def _render_step_env(
    step: Process,
    deps: dict[str, FromMainDependency | FromStepDependency],
    main_step: Process,
) -> str:
    lines = []

    for input_name in step.description.inputs.keys():
        dep = deps[input_name]
        output_key = dep.get("output", "return_value")
        if dep["type"] == "from_main":
            step_id = main_step.description.id
            lines.append(
                f'''            "{input_name}": "{{{{ ti.xcom_pull(task_ids='{step_id}')['{output_key}'] }}}}"'''
            )

        elif dep["type"] == "from_step":
            output_key = dep.get("output", "return_value")
            lines.append(
                f'''            "{input_name}": "{{{{ ti.xcom_pull(task_ids='{dep["step_id"]}')['{output_key}'] }}}}"'''
            )

    return ",\n".join(lines)


def _render_outputs(step: Process) -> str:
    outputs = step.description.outputs
    if not outputs:
        return "None"
    return repr(list(outputs.keys()))


def render_cmd(
    *,
    func_module: str,
    func_qualname: str,
    inputs: str,
    output_keys: str,
) -> str:
    return f"""
from run_step import main

main(
    func_module="{func_module}",
    func_qualname="{func_qualname}",
    inputs={{
{inputs}
    }},
    output_keys={output_keys}
)
"""
