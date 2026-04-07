#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from datetime import datetime, timedelta
from typing import Annotated

import pytest
from pydantic import Field

from appligator.airflow.gen_workflow_dag import (
    gen_workflow_dag,
)
from appligator.airflow.models import ConfigMapMount, PvcMount
from procodile import ProcessRegistry
from procodile.workflow import FromMain, FromStep, Workflow

registry = ProcessRegistry()


@registry.main(
    id="first_step",
    inputs={"id": Field(title="main input")},
    outputs={
        "a": Field(title="main result", description="The result of the main step"),
    },
)
def first_step(id: str) -> str:
    return id


@first_step.step(
    id="second_step",
    inputs={"id": FromMain(output="a")},
)
def second_step(id: str) -> str:
    return id


@first_step.step(
    id="third_step",
)
def third_step(
    id: Annotated[str, FromStep(step_id="second_step", output="return_value")],
) -> str:
    return id


def test_generate_airflow_dag_from_workflow():
    dag_code = gen_workflow_dag(
        dag_id="first_workflow",
        registry=first_step.registry,
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


@registry.main(id="main")
def main() -> str:
    return "x"


@main.step(id="step1")
def step1(x: Annotated[str, FromMain("f")]) -> str:
    return x


@main.step(id="step2")
def step2(x: Annotated[str, FromMain("p")]) -> str:
    return x


def test_generate_airflow_dag_fails_on_multiple_leaf_steps():
    with pytest.raises(ValueError, match="Expected exactly one leaf task"):
        gen_workflow_dag(
            dag_id="bad_workflow",
            registry=main.registry,
            image="x",
        )


def test_generate_airflow_dag_fails_on_invalid_registry():
    with pytest.raises(TypeError, match="unexpected type for registry: int"):
        gen_workflow_dag(
            dag_id="bad_registry",
            registry=123,  # type: ignore[arg-type]
            image="x",
        )


def test_generate_airflow_dag_fails_on_no_image():
    with pytest.raises(ValueError, match="Image name is required to generate dag."):
        gen_workflow_dag(dag_id="bad_registry", registry=main.registry, image=None)


def test_pvc_mount_rendered_in_dag():
    dag_code = gen_workflow_dag(
        dag_id="first_workflow",
        registry=first_step.registry,
        image="example:latest",
        pvc_mounts=[
            PvcMount(name="my-output", claim_name="my-pvc", mount_path="/mnt/output")
        ],
    )
    assert "from kubernetes.client import models as k8s" in dag_code
    assert (
        "volumes=[k8s.V1Volume(name='my-output', "
        "persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name='my-pvc'))]"
    ) in dag_code
    assert (
        "volume_mounts=[k8s.V1VolumeMount(name='my-output', mount_path='/mnt/output')]"
        in dag_code
    )


def test_config_map_mount_without_sub_path_rendered_in_dag():
    dag_code = gen_workflow_dag(
        dag_id="first_workflow",
        registry=first_step.registry,
        image="example:latest",
        config_map_mounts=[
            ConfigMapMount(
                name="my-cm", config_map_name="my-config", mount_path="/etc/config"
            )
        ],
    )
    assert "from kubernetes.client import models as k8s" in dag_code
    assert (
        "volumes=[k8s.V1Volume(name='my-cm', config_map=k8s.V1ConfigMapVolumeSource(name='my-config'))]"
    ) in dag_code
    assert (
        "volume_mounts=[k8s.V1VolumeMount(name='my-cm', mount_path='/etc/config')]"
        in dag_code
    )
    assert "sub_path" not in dag_code


def test_config_map_mount_with_sub_path_rendered_in_dag():
    dag_code = gen_workflow_dag(
        dag_id="first_workflow",
        registry=first_step.registry,
        image="example:latest",
        config_map_mounts=[
            ConfigMapMount(
                name="settings",
                config_map_name="app-settings",
                mount_path="/app/settings.yaml",
                sub_path="settings.yaml",
            )
        ],
    )
    assert (
        "k8s.V1VolumeMount(name='settings', mount_path='/app/settings.yaml', sub_path='settings.yaml')"
    ) in dag_code


def test_pvc_and_config_map_mounts_combined():
    dag_code = gen_workflow_dag(
        dag_id="first_workflow",
        registry=first_step.registry,
        image="example:latest",
        pvc_mounts=[
            PvcMount(name="data", claim_name="data-pvc", mount_path="/mnt/data")
        ],
        config_map_mounts=[
            ConfigMapMount(name="cfg", config_map_name="my-cfg", mount_path="/etc/cfg")
        ],
    )
    assert "k8s.V1PersistentVolumeClaimVolumeSource(claim_name='data-pvc')" in dag_code
    assert "k8s.V1ConfigMapVolumeSource(name='my-cfg')" in dag_code
    assert "k8s.V1VolumeMount(name='data', mount_path='/mnt/data')" in dag_code
    assert "k8s.V1VolumeMount(name='cfg', mount_path='/etc/cfg')" in dag_code
