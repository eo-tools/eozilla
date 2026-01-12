from typing import Annotated

from graphviz import Source
from pydantic import Field

from gavicore.util.request import ExecutionRequest
from procodile import Job
from procodile.workflow import WorkflowRegistry, FromMain, FromStep, \
    Workflow

workflow_registry = WorkflowRegistry()
first_workflow = workflow_registry.get_or_create_workflow(id="first_workflow")

@first_workflow.main(
    id="first_step",
    inputs={
        "id": Field(title="main input")
    },
    outputs={
        "a": Field(title="main result", description="The result of the main step")
    },
)
def first_step(id: str) -> str:
    from workflow_funcs import fun_a
    return fun_a(id)


@first_workflow.step(
    id="second_step",
    inputs={"id": FromMain(output="a")},
)
def second_step(id: str) -> str:
    from workflow_funcs import fun_b
    return fun_b(id)


@first_workflow.step(
    id="third_step",
)
def third_step(
    id: Annotated[str, FromStep(step_id="second_step", output="return_value")]
) -> Annotated[str, Field(title="Output from Third Step")]:
    from workflow_funcs import fun_c
    return fun_c(id)


@first_workflow.step(
    id="fourth_step",
    outputs={
        "some_str": Field(title="Some Str"),
    }
)
def fourth_step(
    id: Annotated[str, FromStep(step_id="third_step", output="return_value")]
) -> str:
    from workflow_funcs import fun_d
    return fun_d(id)


@first_workflow.step(
    id="fifth_step",
    outputs={
        "some_str": Field(title="Some Str"),
    }
)
def fifth_step(
    id: Annotated[str, FromStep(step_id="third_step", output="return_value")],
    id2: Annotated[str, FromMain(output="a")],
) -> tuple[str, str]:
    from workflow_funcs import fun_e
    return fun_e(id, id2)


@first_workflow.step(
    id="sixth_step",
    outputs={
        "final": Field(title="Final output"),
    }
)
def sixth_step(
    id: Annotated[
        tuple[str, str],
        FromStep(step_id="fifth_step", output="some_str"),
    ]
) -> tuple[str, str]:
    from workflow_funcs import fun_f
    return fun_f(id)

#####################


if __name__ == "__main__":
    print(first_workflow)
    order = first_workflow.execution_order
    print(order)
    print(first_workflow.visualize_workflow())
    # render dag
    dot_str = Workflow.visualize_workflow(first_workflow)
    src = Source(dot_str)
    src.render("pipeline", format="png", view=True)

    execution_request = ExecutionRequest.create(
        process_id=first_workflow.id,
        inputs=["id=hi",],
    )

    # create and run job
    job = Job.create(first_workflow, request=execution_request)
    job.run()
