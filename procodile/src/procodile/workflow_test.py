from pydantic import Field
from pydantic.fields import FieldInfo
from typing_extensions import Annotated

from procodile.registry import WorkflowRegistry, FromMain, WorkflowDefinition, FromStep

workflow_registry = WorkflowRegistry()
first_workflow = workflow_registry.workflow(id="first_workflow")


@first_workflow.main(
    id="first_step",
    outputs=({
        "id": FieldInfo(
            description="Main result",
            default="hello world")
        }
))
def fun_a(id: str) -> str:
    return id

@first_workflow.step(
    id="second_step",
    inputs={"id": FromMain("a")}
)
def fun_b(id: str) -> str:
    return id

from collections import defaultdict, deque

def build_dependency_graph(workflow: WorkflowDefinition):
    graph = defaultdict(set)
    in_degree = defaultdict(int)

    in_degree["main"] = 0
    for step_id in workflow._steps:
        in_degree[step_id] = 0

    for step_id, entry in workflow._steps.items():
        deps = entry["dependencies"]
        for dep in deps.values():
            src = dep["step_id"]
            if src != "main" and src not in workflow._steps:
                raise ValueError(f"Unknown dependency step: {src}")
            dst = step_id

            if dst not in graph[src]:
                graph[src].add(dst)
                in_degree[dst] += 1

    return graph, in_degree

def topological_sort(workflow: WorkflowDefinition) -> list[str]:
    graph, in_degree = build_dependency_graph(workflow)

    queue = deque(
        node for node, degree in in_degree.items()
        if degree == 0
    )

    order = []

    while queue:
        node = queue.popleft()
        order.append(node)

        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(in_degree):
        remaining = [
            node for node, degree in in_degree.items()
            if degree > 0
        ]
        raise ValueError(
            f"Workflow contains a cycle involving: {remaining}"
        )

    return order

order = topological_sort(first_workflow)

if __name__ == "__main__":
    print(first_workflow)
    print(first_workflow._main["first_step"])
    print(first_workflow._steps["second_step"])
    print(fun_a)
    print(fun_b)
    print(order)
