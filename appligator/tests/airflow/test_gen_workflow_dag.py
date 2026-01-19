from datetime import datetime, timedelta
from typing import Annotated

import pytest
from pydantic import Field

from appligator.airflow.gen_workflow_dag import (
    gen_workflow_dag,
)
from procodile.workflow import FromMain, FromStep, Workflow

first_workflow = Workflow(id="first_workflow")


@first_workflow.main(
    id="first_step",
    inputs={"id": Field(title="main input")},
    outputs={
        "a": Field(title="main result", description="The result of the main step"),
    },
)
def first_step(id: str) -> str:
    return id


@first_workflow.step(
    id="second_step",
    inputs={"id": FromMain(output="a")},
)
def second_step(id: str) -> str:
    return id


@first_workflow.step(
    id="third_step",
)
def third_step(
    id: Annotated[str, FromStep(step_id="second_step", output="return_value")],
) -> str:
    return id


def test_generate_airflow_dag_from_workflow():
    dag_code = gen_workflow_dag(
        dag_id="first_workflow",
        registry=first_workflow.registry,
        image="example:latest",
    )
    start_date = (datetime.now() - timedelta(days=1)).date().isoformat()
    assert dag_code == (
        "import json\n"
        "from datetime import datetime\n"
        "\n"
        "from airflow import DAG\n"
        "from airflow.models.param import Param\n"
        "from airflow.providers.standard.operators.python import PythonOperator\n"
        "from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator\n"
        "\n"
        "\n"
        "with DAG(\n"
        '    dag_id="first_workflow",\n'
        f'    start_date=datetime.fromisoformat("{start_date}"),\n'
        "    schedule=None,\n"
        "    catchup=False,\n"
        "    is_paused_upon_creation=False,\n"
        "    params={\n"
        "    \"id\": Param(type='string', title='main input')\n"
        "    },\n"
        ") as dag:\n"
        "\n"
        "    tasks = {}\n"
        "\n"
        "\n"
        '    tasks["first_step"] = KubernetesPodOperator(\n'
        '        task_id="first_step",\n'
        '        image="example:latest",\n'
        '        cmds=["python", "/app/run_step.py"],\n'
        "        arguments=[json.dumps({\n"
        '            "func_module": "tests.airflow.test_gen_workflow_dag",\n'
        '            "func_qualname": "first_step",\n'
        '            "inputs": {"id": "{{ params.id }}"},\n'
        "            \"output_keys\": ['a'],\n"
        "        })],\n"
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        "\n"
        '    tasks["second_step"] = KubernetesPodOperator(\n'
        '        task_id="second_step",\n'
        '        image="example:latest",\n'
        '        cmds=["python", "/app/run_step.py"],\n'
        "        arguments=[json.dumps({\n"
        '            "func_module": "tests.airflow.test_gen_workflow_dag",\n'
        '            "func_qualname": "second_step",\n'
        '            "inputs": {"id": "{{ '
        "ti.xcom_pull(task_ids='first_step')['a'] }}\"},\n"
        "            \"output_keys\": ['return_value'],\n"
        "        })],\n"
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        "\n"
        '    tasks["third_step"] = KubernetesPodOperator(\n'
        '        task_id="third_step",\n'
        '        image="example:latest",\n'
        '        cmds=["python", "/app/run_step.py"],\n'
        "        arguments=[json.dumps({\n"
        '            "func_module": "tests.airflow.test_gen_workflow_dag",\n'
        '            "func_qualname": "third_step",\n'
        '            "inputs": {"id": "{{ '
        "ti.xcom_pull(task_ids='second_step')['return_value'] }}\"},\n"
        "            \"output_keys\": ['return_value'],\n"
        "        })],\n"
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        "\n"
        "    def _final_step_callable(ti, upstream_task_id):\n"
        "        return ti.xcom_pull(task_ids=upstream_task_id)\n"
        "    \n"
        '    tasks["__procodile_final_step__"] = PythonOperator(\n'
        '        task_id="__procodile_final_step__",\n'
        "        python_callable=_final_step_callable,\n"
        "        op_kwargs={\n"
        '            "upstream_task_id": "third_step"\n'
        "        },\n"
        "        do_xcom_push=True\n"
        "    )\n"
        "\n"
        '    tasks["first_step"] >> tasks["second_step"]\n'
        '    tasks["second_step"] >> tasks["third_step"]\n'
        '    tasks["third_step"] >> tasks["__procodile_final_step__"]\n'
        "\n"
    )


wf = Workflow(id="bad_workflow")


@wf.main(id="main")
def main() -> str:
    return "x"


@wf.step(id="step1")
def step1(x: Annotated[str, FromMain("f")]) -> str:
    return x


@wf.step(id="step2")
def step2(x: Annotated[str, FromMain("p")]) -> str:
    return x


def test_generate_airflow_dag_fails_on_multiple_leaf_steps():
    with pytest.raises(ValueError, match="Expected exactly one leaf task"):
        gen_workflow_dag(
            dag_id="bad_workflow",
            registry=wf.registry,
            image="x",
        )


def test_generate_airflow_dag_fails_on_invalid_registry():
    with pytest.raises(TypeError, match="unexpected type for registry: int"):
        gen_workflow_dag(
            dag_id="bad_registry",
            registry=123,
            image="x",
        )
