from typing import Literal

from pydantic import BaseModel, Field

Runtime = Literal[
    "kubernetes",
    "syn-python",
]

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

    # Data flow
    inputs: dict[str, str]
    outputs: list[str] = Field(default_factory=list)

    depends_on: list[str] = None

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
