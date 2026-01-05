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
def fun_a(id: str) -> str:
    print("ran from main:::", id)
    return id

@first_workflow.step(
    id="second_step",
    inputs={"id": FromMain(output="a")},
    # outputs=("res",),
)
def fun_b(id: str) -> str:
    print("ran from second_step:::", id * 2)
    return id * 2


@first_workflow.step(
    id="third_step",
)
def fun_c(id: Annotated[str, FromStep(step_id="second_step", output="return_value")])\
    -> Annotated[str, Field(title="Output from Third Step")]:
    print("ran from third_step:::", id  + "hello")
    return id + "hello"

@first_workflow.step(
    id="fourth_step",
    outputs={
        "some_str": Field(title="Some Str"),
    }
)
def fun_d(id: Annotated[str, FromStep(step_id="third_step", output="return_value")])\
    -> str:
    print("ran from fourth_step:::", id  + "world")
    return id + "world"

@first_workflow.step(
    id="fifth_step",
    outputs={
        "some_str": Field(title="Some Str"),
    }
)
def fun_e(id: Annotated[str, FromStep(step_id="third_step", output="return_value")],
          id2: Annotated[str, FromMain(output="a")] = "id2")\
    -> tuple[str, str]:
    print("ran from fifth_step:::", id, id2)
    return id, id2

@first_workflow.step(
    id="sixth_step",
    outputs={
        "final": Field(title="Final output"),
    }
)
def fun_f(id: Annotated[tuple[str, str], FromStep(step_id="fifth_step",
                                              output="some_str")])\
    -> tuple[str, str]:
    print("ran from sixth_step:::", id)
    return id

#####################


if __name__ == "__main__":
    print(first_workflow)
    # print(first_workflow._main["first_step"])
    # print(first_workflow._steps["second_step"])
    # print(fun_a)
    # print(fun_b)
    order = first_workflow.execution_order
    print(order)
    print(first_workflow.visualize_workflow())
    # render dag
    dot_str = Workflow.visualize_workflow(first_workflow)
    src = Source(dot_str)
    # src.render("pipeline", format="png", view=True)
    execution_request = ExecutionRequest.create(
        process_id=first_workflow.id,
        inputs=["id=hi",],
    )
    job = Job.create(first_workflow, request=execution_request)
    job.run()
