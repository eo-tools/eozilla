from typing import Annotated

import pytest
from pydantic import Field

from appligator.airflow.gen_workflow_dag import gen_workflow_dag
from procodile.workflow import Workflow, FromMain, FromStep

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

    dag_code = gen_workflow_dag(dag_id="first_workflow",
                                registry=first_workflow.registry,
                                image="example:latest", output_dir="/tmp/test-dags")

    assert dag_code == (
        "from datetime import datetime\n"
        "import os\n"
        "\n"
        "from airflow import DAG\n"
        "from airflow.models.param import Param\n"
        "from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator\n"
        "from airflow.operators.python import PythonOperator\n"
        "\n"
        "def _final_step_callable(ti, upstream_task_id):\n"
        "    return ti.xcom_pull(task_ids=upstream_task_id)\n"
        "\n"
        "with DAG(\n"
        "    dag_id=\"first_workflow\",\n"
        "    start_date=datetime(2026, 1, 1),\n"
        "    schedule=None,\n"
        "    catchup=False,\n"
        "    render_template_as_native_obj=True,\n"
        "    params={\n"
        "        \"id\": Param(None, type=\"string\")\n"
        "    },\n"
        "    is_paused_upon_creation=False,\n"
        ") as dag:\n"
        "\n"
        "    tasks = {}\n"
        "\n"
        "    tasks[\"first_step\"] = KubernetesPodOperator(\n"
        "        task_id=\"first_step\",\n"
        "        name=\"first-step\",\n"
        "        image=\"example:latest\",\n"
        "        cmds=[\"python\", \"-c\", \"from run_step import main; main()\"],\n"
        "        env_vars={\n"
        "            \"STEP_FUNC_MODULE\": \"tests.airflow.test_gen_workflow_dag\",\n"
        "            \"STEP_FUNC_QUALNAME\": \"first_step\",\n"
        "            \"STEP_OUTPUT_KEYS\": \"a\",\n"
        "            \"STEP_INPUT_id\": \"{{ params.id }}\"\n"
        "        },\n"
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        "    tasks[\"second_step\"] = KubernetesPodOperator(\n"
        "        task_id=\"second_step\",\n"
        "        name=\"second-step\",\n"
        "        image=\"example:latest\",\n"
        "        cmds=[\"python\", \"-c\", \"from run_step import main; main()\"],\n"
        "        env_vars={\n"
        "            \"STEP_FUNC_MODULE\": \"tests.airflow.test_gen_workflow_dag\",\n"
        "            \"STEP_FUNC_QUALNAME\": \"second_step\",\n"
        "            \"STEP_OUTPUT_KEYS\": \"return_value\",\n"
        "            \"STEP_INPUT_id\": \"{{ ti.xcom_pull(task_ids='first_step')['a'] }}\"\n"
        "        },\n"
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        "    tasks[\"third_step\"] = KubernetesPodOperator(\n"
        "        task_id=\"third_step\",\n"
        "        name=\"third-step\",\n"
        "        image=\"example:latest\",\n"
        "        cmds=[\"python\", \"-c\", \"from run_step import main; main()\"],\n"
        "        env_vars={\n"
        "            \"STEP_FUNC_MODULE\": \"tests.airflow.test_gen_workflow_dag\",\n"
        "            \"STEP_FUNC_QUALNAME\": \"third_step\",\n"
        "            \"STEP_OUTPUT_KEYS\": \"return_value\",\n"
        "            \"STEP_INPUT_id\": \"{{ ti.xcom_pull(task_ids='second_step')['return_value'] }}\"\n"
        "        },\n"
        "        do_xcom_push=True,\n"
        "    )\n"
        "\n"
        "    tasks[\"final_step\"] = PythonOperator(\n"
        "        task_id=\"final_step\",\n"
        "        python_callable=_final_step_callable,\n"
        "        op_kwargs={\n"
        "            \"upstream_task_id\": \"third_step\"\n"
        "        },\n"
        "        do_xcom_push=True\n"
        "    )\n"
        "    \n"
        "    tasks[\"first_step\"] >> tasks[\"second_step\"]\n"
        "    tasks[\"second_step\"] >> tasks[\"third_step\"]\n"
        "    tasks[\"third_step\"] >> tasks[\"final_step\"]\n"
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
        )


def test_generate_airflow_dag_fails_on_invalid_registry():
    with pytest.raises(TypeError, match="unexpected type for registry: int"):
        gen_workflow_dag(
            dag_id="bad_registry",
            registry=123,
            image="x",
        )
