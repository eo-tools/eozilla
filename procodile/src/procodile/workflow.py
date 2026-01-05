#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from collections import defaultdict, deque
from collections.abc import Iterator
from typing import Callable, Optional, get_origin, Annotated, get_args, DefaultDict, Any

from pydantic.fields import FieldInfo

from gavicore.models import InputDescription, OutputDescription

from .process import Process

class FromMain:
    def __init__(self, output: str):
        self.output = output

    def to_dict(self):
        return {"output": self.output, "type": "from_main"}

class FromStep:
    def __init__(self, step_id: str, output: str):
        self.step_id = step_id
        self.output = output

    def to_dict(self):
        return {"step_id": self.step_id, "output": self.output, "type": "from_step"}


class WorkflowRegistry:
    def __init__(self):
        self._workflows: dict[str, "WorkflowDefinition"] = {}

    def __getitem__(self, workflow_id: str, /) -> "WorkflowDefinition":
        return self._workflows[workflow_id]

    def __len__(self) -> int:
        return len(self._workflows)

    def __iter__(self) -> Iterator[str]:
        return iter(self._workflows)

    def get_or_create_workflow(self, id: str) -> "WorkflowDefinition":
        if id in self._workflows:
            return self._workflows[id]
        definition = Workflow(id)
        self._workflows[id] = definition
        return definition

class WorkflowStepRegistry:
    """Handles storage of main process and workflow steps."""
    def __init__(self):
        self.main: dict[str, Process] = {}
        self.steps: dict[str, Process | dict] = {}

    def register_main(self, fn: Callable, **kwargs) -> Callable:
        main_process = Process.create(fn, **kwargs)
        self.main[main_process.description.id] = main_process
        return fn

    def register_step(self, fn: Callable, **kwargs) -> Callable:
        signature = inspect.signature(fn)
        dependencies = {}
        schema_inputs = {}

        for name, param in signature.parameters.items():
            annotation, metadata = unwrap_annotated(param.annotation)
            for meta in metadata:
                if isinstance(meta, (FromMain, FromStep)):
                    dependencies[name] = meta.to_dict()
                else:
                    schema_inputs[name] = annotation

        # Merge user-provided inputs
        inputs = kwargs.pop("inputs", None)
        if inputs:
            for name, value in inputs.items():
                if isinstance(value, (FromMain, FromStep)):
                    if name in dependencies:
                        raise ValueError(f"Duplicate dependency definition for input {name!r}")
                    dependencies[name] = value.to_dict()
                else:
                    schema_inputs[name] = value

        step = Process.create(fn, inputs=schema_inputs, **kwargs)
        self.steps[step.description.id] = {"step": step, "dependencies": dependencies}
        return fn


class Workflow:
    """A workflow is just multiple steps (processes) connected to each other without
        any loops.

        Each step is basically a process as per current OGC Part 3 draft.
        """
    def __init__(self, id: str):
        self.id = id

        self.registry = WorkflowStepRegistry()
        self.graph: DependencyGraph | None = None

        # Properties to access the workflow execution order
        self.order: list[dict | None] | None = None
        self.dep_graph: defaultdict[str, set[str]] = defaultdict(set)

    @property
    def execution_order(self) -> tuple[
        list[dict | None] | None, defaultdict[str, set[str]]]:
        if not self.graph:
            self.graph = self._get_graph()
        self.order, self.dep_graph = self.graph.topological_sort()

        return self.order, self.dep_graph

    def _get_graph(self):
        return DependencyGraph(self.registry.main, self.registry.steps)

    def visualize_workflow(self) -> str:
        _, deps = self.execution_order
        print(deps)
        lines = ["digraph pipeline {", "rankdir=LR;"]
        for node in deps:
            lines.append(f'"{node}";')
        for node, targets in deps.items():
            for t in targets:
                lines.append(f'"{node}" -> "{t}";')
        lines.append("}")
        return "\n".join(lines)

    def run(self, **function_kwargs):
        order, graph = self.execution_order
        for step_name in order:
            print(step_name)
            main_process_key = next(iter(self.registry.main))
            if step_name == main_process_key:
                main_process = self.registry.main[main_process_key]
                result = main_process.function(**function_kwargs)
            else:
                step = self.registry.steps[step_name]
                # print(step["step"].function)
                result=step["step"].function(**function_kwargs)
                print(result)

            # result = step_meta.func( **function_kwargs)


    def main(self, fn=None, /, **kwargs):
        if fn is None:
            return lambda f: self.registry.register_main(f, **kwargs)
        return self.registry.register_main(fn, **kwargs)

    def step(self, fn=None, /, **kwargs):
        if fn is None:
            return lambda f: self.registry.register_step(f, **kwargs)
        return self.registry.register_step(fn, **kwargs)


    # def step(self,
    #     function: Optional[Callable] = None,
    #     /,
    #     *,
    #     id: Optional[str] = None,
    #     version: Optional[str] = None,
    #     title: Optional[str] = None,
    #     description: Optional[str] = None,
    #     inputs: Optional[dict[str, FieldInfo | InputDescription | FromMain |
    #                                FromStep]] = None,
    #     outputs: tuple[str] | dict[str, FieldInfo | OutputDescription] | None = None,
    #     inputs_arg: str | bool = False,
    # ) -> Callable[[Callable], Callable] | Callable:
    #     def register_step(fn: Callable):
    #         schema_inputs = {}
    #         dependencies = {}
    #         signature = inspect.signature(fn)
    #         for name, param in signature.parameters.items():
    #             annotation, metadata = unwrap_annotated(param.annotation)
    #             for meta in metadata:
    #                 if isinstance(meta, (FromMain, FromStep)):
    #                     dependencies[name] = meta.to_dict()
    #                 else:
    #                     schema_inputs[name] = annotation
    #             # print("annotation", param, annotation)
    #         if inputs:
    #             for name, value in inputs.items():
    #                 if isinstance(value, (FromMain, FromStep)):
    #                     if name in dependencies:
    #                         raise ValueError(
    #                             f"Duplicate dependency definition for input {name!r}"
    #                         )
    #                     dependencies[name] = value.to_dict()
    #                 else:
    #                     schema_inputs[name] = value
    #         step = Process.create(
    #             fn,
    #             id=id,
    #             version=version,
    #             title=title,
    #             description=description,
    #             inputs=schema_inputs,
    #             outputs=outputs,
    #             inputs_arg=inputs_arg,
    #         )
    #         self._steps[step.description.id] = {
    #                                 "step": step,
    #                                 "dependencies": dependencies
    #                             }
    #
    #         return fn
    #
    #     if function is not None:
    #         return register_step(function)
    #     else:
    #         return register_step

class DependencyGraph:
    def __init__(self, main: dict[str, Process], steps: dict[str, dict[str, Any]]):
        self.main = main
        self.steps = steps

    def build_dependency_graph(self) -> tuple[
        defaultdict[str, set], defaultdict[str, int]]:
        graph = defaultdict(set)
        in_degree = defaultdict(int)

        if len(self.main) != 1:
            raise ValueError(
                f"Workflow must have exactly ONE main, found {len(self.main)}"
            )

        # in_degree["main"] = 0
        for step_id in self.main:
            in_degree[step_id] = 0

        for step_id in self.steps:
            in_degree[step_id] = 0

        for step_id, entry in self.steps.items():
            deps = entry.get("dependencies", {})

            for param, dep in deps.items():
                dep_type = dep.get("type")

                if dep_type == "from_main":
                    main = next(iter(self.main.values()))
                    src = main.description.id
                    outputs = main.description.outputs or {}
                    expected = dep.get("output", "return_value")

                    if expected not in outputs and expected != "return_value":
                        raise ValueError(
                            f"Step '{step_id}' expects output '{expected}' "
                            f"from main, but main exposes "
                            f"{tuple(outputs.keys()) or ('return_value',)}"
                        )

                elif dep_type == "from_step":
                    src = dep.get("step_id")

                    if src not in self.steps:
                        raise ValueError(
                            f"Step '{step_id}' depends on unknown step '{src}'"
                        )

                    src_step = self.steps[src]["step"]
                    outputs = src_step.description.outputs or {}
                    expected = dep.get("output", "return_value")

                    if outputs:
                        if expected not in outputs:
                            raise ValueError(
                                f"Step '{step_id}' expects output '{expected}' "
                                f"from step '{src}', but available outputs are "
                                f"{list(outputs.keys())}"
                            )

                else:
                    raise ValueError(
                        f"Invalid dependency type '{dep_type}' "
                        f"in step '{step_id}' param '{param}'"
                    )

                if step_id not in graph[src]:
                    graph[src].add(step_id)
                    in_degree[step_id] += 1

        return graph, in_degree

    def topological_sort(self) -> tuple[list[dict | None] | None, defaultdict[str, set[str]]]:
        graph, in_degree = self.build_dependency_graph()
        queue = deque(node for node, degree in in_degree.items() if degree == 0)

        order: list[dict | None] | None = []

        while queue:
            node = queue.popleft()
            order.append(node)

            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(in_degree):
            remaining = [node for node, degree in in_degree.items() if degree > 0]
            raise ValueError(f"Workflow contains a cycle involving: {remaining}")

        return order, graph


def unwrap_annotated(annotation):
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return args[0], list(args[1:])
    return annotation, []



