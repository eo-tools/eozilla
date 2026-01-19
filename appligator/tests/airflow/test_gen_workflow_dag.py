import unittest
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import Field

from appligator.airflow.gen_workflow_dag import (
    gen_workflow_dag,
    _get_param_args,
    _render_main_inputs,
    _render_step_inputs,
    _render_outputs,
    render_cmd,
)
from gavicore.models import InputDescription, Schema
from procodile import Process
from procodile.workflow import FromMain, FromStep, Workflow, FINAL_STEP_ID

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
        output_dir=Path("/tmp/test-dags"),
    )

    assert dag_code == (
        "from datetime import datetime\n"
        "\n"
        "from airflow import DAG\n"
        "from airflow.models.param import Param\n"
        "from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator\n"
        "from airflow.providers.standard.operators.python import PythonOperator\n"
        "\n"
        "def _final_step_callable(ti, upstream_task_id):\n"
        "    return ti.xcom_pull(task_ids=upstream_task_id)\n"
        "\n"
        "with DAG(\n"
        '    dag_id="first_workflow",\n'
        "    start_date=datetime(2026, 1, 1),\n"
        "    schedule=None,\n"
        "    catchup=False,\n"
        "    render_template_as_native_obj=True,\n"
        "    params={\n"
        "    'id': Param(type='string', title='main input'),\n"
        "    },\n"
        "    is_paused_upon_creation=False,\n"
        ") as dag:\n"
        "\n"
        "    tasks = {}\n"
        "\n"
        '    tasks["first_step"] = KubernetesPodOperator(\n'
        '        task_id="first_step",\n'
        '        name="first-step",\n'
        '        image="example:latest",\n'
        '        cmds=[\n'
        '            "python", \n'
        '            "-c", \n'
        "            '\\nfrom run_step import main\\n\\nmain(\\n    "
        'func_module="tests.airflow.test_gen_workflow_dag",\\n    '
        'func_qualname="first_step",\\n    inputs={\\n            "id": "{{ params.id '
        '}}"\\n    },\\n    output_keys=[\\\'a\\\']\\n)\\n\'\n'
        '        ],\n'
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        '    tasks["second_step"] = KubernetesPodOperator(\n'
        '        task_id="second_step",\n'
        '        name="second-step",\n'
        '        image="example:latest",\n'
        '        cmds=[\n'
        '            "python", \n'
        '            "-c", \n'
        "            '\\nfrom run_step import main\\n\\nmain(\\n    "
        'func_module="tests.airflow.test_gen_workflow_dag",\\n    '
        'func_qualname="second_step",\\n    inputs={\\n            "id": "{{ '
        'ti.xcom_pull(task_ids=\\\'first_step\\\')[\\\'a\\\'] }}"\\n    },\\n    '
        "output_keys=[\\'return_value\\']\\n)\\n'\n"
        '        ],\n'
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        '    tasks["third_step"] = KubernetesPodOperator(\n'
        '        task_id="third_step",\n'
        '        name="third-step",\n'
        '        image="example:latest",\n'
        '        cmds=[\n'
        '            "python", \n'
        '            "-c", \n'
        "            '\\nfrom run_step import main\\n\\nmain(\\n    "
        'func_module="tests.airflow.test_gen_workflow_dag",\\n    '
        'func_qualname="third_step",\\n    inputs={\\n            "id": "{{ '
        'ti.xcom_pull(task_ids=\\\'second_step\\\')[\\\'return_value\\\'] }}"\\n    '
        "},\\n    output_keys=[\\'return_value\\']\\n)\\n'\n"
        '        ],\n'
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        '    tasks["__procodile_final_step__"] = PythonOperator(\n'
        '        task_id="__procodile_final_step__",\n'
        "        python_callable=_final_step_callable,\n"
        "        op_kwargs={\n"
        '            "upstream_task_id": "third_step"\n'
        "        },\n"
        "        do_xcom_push=True\n"
        "    )\n"
        "    \n"
        '    tasks["first_step"] >> tasks["second_step"]\n'
        '    tasks["second_step"] >> tasks["third_step"]\n'
        '    tasks["third_step"] >> tasks["__procodile_final_step__"]\n'
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
    with pytest.raises(ValueError, match="Expected exactly one leaf step"):
        gen_workflow_dag(
            dag_id="bad_workflow",
            registry=wf.registry,
            image="x",
            output_dir=Path("")
        )


def test_generate_airflow_dag_fails_on_invalid_registry():
    with pytest.raises(TypeError, match="unexpected type for registry: int"):
        gen_workflow_dag(
            dag_id="bad_registry",
            registry=123,
            image="x",
            output_dir=Path("")
        )

class TestRenderingHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Workflow(id="first_workflow")

        @cls.workflow.main(
            id="first_step",
            inputs={"id": Field(title="main input")},
            outputs={
                "a": Field(
                    title="main result",
                    description="The result of the main step",
                ),
            },
        )
        def first_step(id: str) -> str:
            return id

        @cls.workflow.step(
            id="second_step",
            inputs={"id": FromMain(output="a")},
        )
        def second_step(id: str) -> str:
            return id

        @cls.workflow.step(id="third_step")
        def third_step(
            id: Annotated[str, FromStep(step_id="second_step", output="return_value")],
        ) -> str:
            return id

    def test_get_param_args_main_input(self):
        input_desc = next(iter(self.workflow.registry.main.values())).description.inputs["id"]

        result = _get_param_args(input_desc)

        self.assertIn("title='main input'", result)
        self.assertIn("type='string'", result)

    def test_get_param_args(self):
        desc = InputDescription(
            schema=Schema(**{
                "default": 10,
                "type": "integer",
                "minimum": 0.0,
                "maximum": 100,
            }),
            title="Age",
            description="User age",
        )

        result = _get_param_args(desc)

        self.assertEqual(
            result,
            "default=10, type='integer', title='Age', description='User age', "
            "maximum=100.0, minimum=0.0",
        )

    def test_render_main_env(self):
        param_specs = [
            "'id': Param(default='hithere', type='string')",
            "'id2': Param(default='watchadoing', type='string')",
        ]

        result = _render_main_inputs(param_specs)

        self.assertEqual(
            result,
            '            "id": "{{ params.id }}",\n'
            '            "id2": "{{ params.id2 }}"'
        )

    def test_render_step_env(self):
        results = []
        steps_dict = self.workflow.registry.steps
        for step_id, meta in steps_dict.items():
            if step_id == FINAL_STEP_ID:
                continue

            step = meta["step"]
            deps = meta["dependencies"]

            result = _render_step_inputs(step=step, deps=deps, main_step=next(
                iter(self.workflow.registry.main.values())))
            results.append(result)
        self.assertEqual(
            results,
            [
                '            "id": "{{ ti.xcom_pull(task_ids=\'first_step\')[\'a\'] }}"',
                '            "id": "{{ ti.xcom_pull(task_ids=\'second_step\')[\'return_value\'] }}"']
        )

    def test_render_outputs_main(self):
        result = _render_outputs(next(iter(self.workflow.registry.main.values())))
        self.assertEqual(result, "['a']")

    def test_render_outputs_no_outputs(self):
        step = next(iter(self.workflow.registry.steps.values()))['step']
        result = _render_outputs(step)
        self.assertEqual(result, "['return_value']")

    def test_render_cmd(self):
        result = render_cmd(
            func_module="my.mod",
            func_qualname="do_thing",
            inputs='            "x": "{{ params.x }}"',
            output_keys="['out']",
        )

        self.assertIn('func_module="my.mod"', result)
        self.assertIn('func_qualname="do_thing"', result)
        self.assertIn('"x": "{{ params.x }}"', result)
        self.assertIn("output_keys=['out']", result)
