#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from appligator.airflow.ir import workflow_to_ir
from appligator.airflow.models import ResourceRequirements
from appligator.airflow.renderer import AirflowRenderer
from procodile.workflow import WorkflowStepRegistry


def gen_workflow_dag(
    dag_id: str,
    registry: WorkflowStepRegistry,
    image: str,
    env_from_secrets: list[str] | None = None,
    resources: ResourceRequirements | None = None,
) -> str:
    """Generates a fully-formed Airflow DAG Python file."""

    if not isinstance(registry, WorkflowStepRegistry):
        raise TypeError(f"unexpected type for registry: {type(registry).__name__}")

    if not image:
        raise ValueError("Image name is required to generate dag.")

    # operator-agnostic intermediate representation
    ir = workflow_to_ir(
        registry,
        dag_id,
        image_name=image,
        env_from_secrets=env_from_secrets,
        resources=resources,
    )

    dag_code = AirflowRenderer().render(ir)

    return dag_code
