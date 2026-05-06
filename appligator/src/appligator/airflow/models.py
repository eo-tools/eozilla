#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Literal

from pydantic import BaseModel, Field

Runtime = Literal[
    "kubernetes",
    "syn-python",
]


class PvcMount(BaseModel):
    """A PersistentVolumeClaim volume with its mount point."""

    name: str
    claim_name: str
    mount_path: str


class ConfigMapMount(BaseModel):
    """A ConfigMap volume with its mount point."""

    name: str
    config_map_name: str
    mount_path: str
    sub_path: str | None = None


class ResourceRequirements(BaseModel):
    """
    CPU and memory resource requests and limits for a container.

    Values follow the Kubernetes quantity syntax (e.g. "500m", "2", "256Mi", "1Gi").
    All fields are optional; only the non-None ones are emitted into the generated DAG.
    """

    cpu_request: str | None = None
    memory_request: str | None = None
    cpu_limit: str | None = None
    memory_limit: str | None = None


class TaskIR(BaseModel):
    """
    Operator-agnostic description of a single executable task.

    TaskIR (Task Intermediate Representation) is consumed by backend
    renderer -> `AirflowRenderer` and translated into concrete Airflow operators.

    Fields:
        id: Unique task identifier.
        runtime: Execution runtime ("kubernetes", "syn-python", etc.).
        func_module: Python module containing the callable (if applicable).
        func_qualname: Qualified name of the callable (if applicable).
        image: Container image for container-based runtimes (if applicable).
        command: Optional command override.
        env: Optional environment variables.
        resources: Optional CPU/memory requests and limits.
        inputs: Mapping of input names to param:/xcom: references.
        outputs: List of output keys produced by the task.
        depends_on: List of upstream task IDs.
    """

    id: str

    runtime: Runtime

    # Python runtime
    func_module: str | None = None
    func_qualname: str | None = None

    # Container runtime
    image: str | None = None
    command: list[str] | None = None
    env: dict[str, str] | None = None
    env_from_secrets: list[str] | None = None
    resources: ResourceRequirements | None = None
    pvc_mounts: list[PvcMount] = Field(default_factory=list)
    config_map_mounts: list[ConfigMapMount] = Field(default_factory=list)

    # Data flow
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)

    depends_on: list[str] | None = None


class WorkflowIR(BaseModel):
    """
    Fully normalized, operator-agnostic workflow description.

    WorkflowIR (Workflow Intermediate Representation) is the single source of
    truth that contains no operator-specific logic and can be rendered into different
    Airflow operators.

    Fields:
        id: Workflow/DAG identifier.
        params: DAG-level parameter definitions.
        tasks: Ordered list of TaskIR objects.
        final_task: ID of the final non-synthetic (actual user-defined) task.
    """

    id: str
    params: dict[str, dict] = Field(default_factory=dict)
    tasks: list[TaskIR]
    final_task: str
