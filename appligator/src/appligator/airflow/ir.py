from typing import Any

from appligator.airflow.models import TaskIR, WorkflowIR
from gavicore.models import InputDescription
from procodile import WorkflowStepRegistry
from procodile.workflow import FINAL_STEP_ID


def workflow_to_ir(
    registry: WorkflowStepRegistry, workflow_id: str, image_name: str = ""
) -> WorkflowIR:
    """
    Convert a WorkflowStepRegistry into a fully normalized WorkflowIR (Workflow
    Intermediate Representation).

    It is the only place that understands (after this step, DAG renderer just uses
    the IR representation):
    - WorkflowStepRegistry
    - Process metadata
    - FromMain / FromStep dependency semantics

    Responsibilities:
    - Extract DAG-level parameters from the main step
    - Normalize task inputs into param:/xcom: references
    - Construct TaskIR objects for all steps
    - Insert a synthetic final task for stable output retrieval
    - Compute task dependency relationships

    The last step with `FINAL_STEP_ID` is a synthetic final step that just passes the
    xcom from the actual last step to its output so that other services can consume
    the output of the dag from a persistent `FINAL_STEP_ID` task_id.

    Args:
        registry: A WorkflowStepRegistry produced by the workflow DSL.
        workflow_id: The DAG/workflow identifier.
        image_name: Optional Container image used for Kubernetes tasks.

    Returns:
        A WorkflowIR representing the complete workflow execution graph.
    """

    main_step = next(iter(registry.main.values()))
    main_step_id = main_step.description.id

    tasks: list[TaskIR] = []

    input_descriptions = main_step.description.inputs or {}

    params: dict[str, dict[str, Any]] = {}

    for name, input_description in input_descriptions.items():
        params[name] = _get_param_schema(input_description)

    tasks.append(
        TaskIR(
            id=main_step_id,
            runtime="kubernetes",
            func_module=main_step.function.__module__,
            func_qualname=main_step.function.__qualname__,
            image=image_name,
            inputs={name: f"param:{name}" for name in params},
            outputs=list((main_step.description.outputs or {}).keys()),
            depends_on=[],
        )
    )

    for step_id, meta in registry.steps.items():
        step = meta["step"]
        deps = meta["dependencies"]

        inputs: dict[str, str] = {}
        depends_on: list[str] = []

        for input_name, dep in deps.items():
            output_key = dep.get("output", "return_value")

            if dep["type"] == "from_main":
                inputs[input_name] = f"xcom:{main_step_id}:{output_key}"
                depends_on.append(main_step_id)

            elif dep["type"] == "from_step":
                upstream = dep["step_id"]
                inputs[input_name] = f"xcom:{upstream}:{output_key}"
                depends_on.append(upstream)

        tasks.append(
            TaskIR(
                id=step_id,
                runtime="kubernetes",
                func_module=step.function.__module__,
                func_qualname=step.function.__qualname__,
                image=image_name,
                inputs=inputs,
                outputs=list((step.description.outputs or {}).keys()),
                depends_on=sorted(set(depends_on)),
            )
        )

    all_task_ids = {t.id for t in tasks}
    upstream_tasks = {d for t in tasks for d in t.depends_on or []}
    leaf_tasks = all_task_ids - upstream_tasks

    if len(leaf_tasks) != 1:
        raise ValueError("Expected exactly one leaf task")

    final_task = next(iter(leaf_tasks))

    tasks.append(
        TaskIR(
            id=FINAL_STEP_ID,
            runtime="syn-python",
            inputs={"upstream_task_id": f"{final_task}"},
            depends_on=[final_task],
        )
    )

    return WorkflowIR(
        id=workflow_id,
        params=params,
        tasks=tasks,
        final_task=final_task,
    )


def _get_param_schema(input_description: InputDescription) -> dict[str, Any]:
    """
    Extract a normalized parameter schema from an InputDescription.

    This function converts an InputDescription into a dictionary suitable
    for constructing an Airflow Param object. Known fields (default, type,
    title, description) are handled explicitly, while all remaining schema
    constraints are preserved and passed through.

    Args:
        input_description: The input description object defining a DAG parameter.

    Returns:
        A dictionary containing parameter configuration for Airflow Param.
    """

    schema = dict(
        input_description.schema_.model_dump(
            mode="json",
            by_alias=True,
            exclude_defaults=True,
            exclude_none=True,
            exclude_unset=True,
        )
    )

    result: dict[str, Any] = {}

    if "default" in schema:
        result["default"] = schema.pop("default")

    if "type" in schema:
        result["type"] = schema.pop("type")

    if input_description.title:
        result["title"] = input_description.title

    if input_description.description:
        result["description"] = input_description.description

    result.update(schema)
    return result
