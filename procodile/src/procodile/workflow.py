#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from collections import defaultdict, deque
from copy import deepcopy
from typing import Annotated, Any, Callable, Literal, TypedDict, get_args, get_origin

from .artifacts import ArtifactStore, ExecutionContext
from .process import Process


class FromMainDependency(TypedDict):
    type: Literal["from_main"]
    output: str


class FromStepDependency(TypedDict):
    type: Literal["from_step"]
    step_id: str
    output: str


DependencySpec = FromMainDependency | FromStepDependency

FINAL_STEP_ID = "final_step"


class StepEntry(TypedDict):
    step: Process
    dependencies: dict[str, DependencySpec]


class FromMain:
    def __init__(self, output: str):
        self.output = output

    def to_dict(self) -> FromMainDependency:
        return {"output": self.output, "type": "from_main"}


class FromStep:
    def __init__(self, step_id: str, output: str):
        self.step_id = step_id
        self.output = output

    def to_dict(self) -> FromStepDependency:
        return {"step_id": self.step_id, "output": self.output, "type": "from_step"}


class WorkflowRegistry:
    def __init__(self):
        self._workflows: dict[str, Workflow] = {}

    def get_or_create_workflow(self, id: str) -> "Workflow":
        if id in self._workflows:
            return self._workflows[id]
        definition = Workflow(id)
        self._workflows[id] = definition
        return definition

    def _as_process(self, workflow: "Workflow") -> Process:
        """This is the facade process object that is returned when the client wants
        to see what processes are available and is also used to run the actual
        workflow"""

        # Exactly one main is required
        if len(workflow.registry.main) != 1:
            raise ValueError(
                f"Workflow {workflow.id!r} must have exactly one main process"
            )

        main = next(iter(workflow.registry.main.values()))

        projected = deepcopy(main)

        # Steps exist -> last step defines outputs
        if workflow.registry.steps:
            order, _ = workflow.execution_order
            last_step_id = order[-2]  # because the step before that is the actual
            # user defined last step.
            last_step = workflow.registry.steps[last_step_id]["step"]
            projected.description.outputs = last_step.description.outputs

        projected.description.id = workflow.id
        projected.function = workflow.run

        return projected

    def get(self, workflow_id: str, default=None) -> Process | None:
        # wf = self._workflows.get(workflow_id)
        # return default if wf is None else self._as_process(wf)

        try:
            return self[workflow_id]
        except KeyError:
            return default

    def values(self):
        # for wf in self._workflows.values():
        #     yield self._as_process(wf)
        for workflow_id in self:
            yield self[workflow_id]

    def items(self):
        # for wf_id, wf in self._workflows.items():
        #     yield wf_id, self._as_process(wf)
        for workflow_id in self:
            yield workflow_id, self[workflow_id]

    # def __getitem__(self, workflow_id: str, /) -> "Workflow":
    #     return self._workflows[workflow_id]

    def __getitem__(self, workflow_id: str) -> Process:
        return self._as_process(self._workflows[workflow_id])

    def __iter__(self):
        # iteration yields keys (dict semantics)
        return iter(self._workflows)

    def __len__(self) -> int:
        return len(self._workflows)

    def __contains__(self, workflow_id: str) -> bool:
        return workflow_id in self._workflows

    # def get(self, workflow_id: str, default=None) -> Process | None:
    #     if workflow_id in self._workflows:
    #         return self[workflow_id]
    #     return default

    def get_workflow(self, workflow_id: str) -> "Workflow":
        """
        INTERNAL API.
        Returns the actual Workflow object.
        """
        return self._workflows[workflow_id]

    def workflows(self):
        """
        INTERNAL API.
        Returns all workflows
        """
        return self._workflows


class WorkflowStepRegistry:
    """Handles storage of main process and workflow steps."""

    def __init__(self):
        self.main: dict[str, Process] = {}
        self.steps: dict[str, StepEntry] = {}

    def register_main(self, fn: Callable, **kwargs) -> Callable:
        main_process = Process.create(fn, **kwargs)
        self.main[main_process.description.id] = main_process
        return fn

    def register_step(self, fn: Callable, **kwargs) -> Callable:
        signature = inspect.signature(fn)
        dependencies = {}

        for name, param in signature.parameters.items():
            annotation, metadata = unwrap_annotated(param.annotation)
            for meta in metadata:
                if isinstance(meta, (FromMain, FromStep)):
                    dependencies[name] = meta.to_dict()
                else:
                    raise ValueError(
                        f"Invalid dependency metadata for input '{name}': {meta!r}"
                    )

        # Merge user-provided inputs
        inputs = kwargs.pop("inputs", None)
        if inputs:
            for name, value in inputs.items():
                if isinstance(value, (FromMain, FromStep)):
                    if name in dependencies:
                        raise ValueError(
                            f"Duplicate dependency definition for input {name!r}"
                        )
                    dependencies[name] = value.to_dict()
                else:
                    raise ValueError(
                        f"Invalid dependency metadata for input '{name}': {meta!r}"
                    )

        step = Process.create(fn, **kwargs)
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
        self.order: list[str] = []
        self.dep_graph: defaultdict[str, set[str]] = defaultdict(set)

    @property
    def execution_order(
        self,
    ) -> tuple[list[str], defaultdict[str, set[str]]]:
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
        store = ArtifactStore()
        ctx = ExecutionContext(store)

        order, graph = self.execution_order
        print("order", order)
        print("graph", graph)
        # Run Main first
        main_id = next(iter(self.registry.main))
        main = self.registry.main[main_id]

        main_result = main.function(**function_kwargs)

        main_outputs = ctx.normalize_outputs(
            result=main_result,
            output_spec=main.description.outputs,
            store=store,
        )

        ctx.main.update(main_outputs)
        outputs = main_outputs

        for step_id in order:
            if step_id == main_id:
                continue

            if step_id == FINAL_STEP_ID:
                # ---- FINAL STEP: collect outputs ----
                outputs = self._collect_final_outputs(ctx, graph)
                ctx.steps[FINAL_STEP_ID] = outputs
                continue

            step_entry = self.registry.steps[step_id]
            step_def = step_entry["step"]
            step_deps = step_entry["dependencies"]
            fn = step_def.function

            kwargs: dict[str, Any] = {}

            sig = inspect.signature(fn)
            annotations = inspect.get_annotations(fn)

            for name, param in sig.parameters.items():
                dep = extract_dependency(annotations.get(name)) or step_deps.get(name)

                if dep is not None:
                    if dep["type"] == "from_main":
                        raw = ctx.main[dep["output"]]

                    elif dep["type"] == "from_step":
                        raw = ctx.steps[dep["step_id"]][dep["output"]]

                    else:
                        raise ValueError(f"Unknown dependency type: {dep}")

                else:
                    if param.default is not inspect.Parameter.empty:
                        raw = param.default
                    else:
                        raise ValueError(
                            f"Missing required argument '{name}' for step '{step_id}'"
                        )

                kwargs[name] = ctx.resolve(raw)

            result = fn(**kwargs)

            outputs = ctx.normalize_outputs(
                result=result,
                output_spec=step_def.description.outputs,
                store=store,
            )

            ctx.steps[step_id] = outputs

        return outputs

    def _collect_final_outputs(self, ctx: ExecutionContext, graph) -> dict[str, Any]:
        """
        Collect outputs from all immediate predecessors of FINAL_STEP.
        Outputs are namespaced by step ID to avoid collisions.
        """

        final_inputs = {}

        # find the upstream step feeding into final_step
        upstream_steps = [
            src for src, targets in graph.items() if FINAL_STEP_ID in targets
        ]

        assert len(upstream_steps) == 1, (
            f"There should be exactly one leaf step, found {len(upstream_steps)}"
        )

        for step_id in upstream_steps:
            if ctx.steps:
                step_outputs = ctx.steps.get(step_id)
            else:
                step_outputs = ctx.main

            if step_outputs is None:
                raise RuntimeError(
                    f"Final step depends on '{step_id}', but no outputs were produced"
                )

            final_inputs = step_outputs

        return final_inputs

    def main(self, fn=None, /, **kwargs):
        if fn is None:
            return lambda f: self.registry.register_main(f, **kwargs)
        return self.registry.register_main(fn, **kwargs)

    def step(self, fn=None, /, **kwargs):
        if fn is None:
            return lambda f: self.registry.register_step(f, **kwargs)
        return self.registry.register_step(fn, **kwargs)


class DependencyGraph:
    def __init__(self, main: dict[str, Process], steps: dict[str, StepEntry]):
        self.main = main
        self.steps = steps

    def build_dependency_graph(
        self,
    ) -> tuple[defaultdict[str, set], defaultdict[str, int]]:
        graph: defaultdict[str, set[str]] = defaultdict(set)
        in_degree = defaultdict(int)

        if len(self.main) != 1:
            raise ValueError(
                f"Workflow must have exactly ONE main, found {len(self.main)}"
            )

        for step_id in self.main:
            in_degree[step_id] = 0

        for step_id in self.steps:
            in_degree[step_id] = 0

        for step_id, entry in self.steps.items():
            deps = entry.get("dependencies", {})

            for param, dep in deps.items():
                if dep["type"] == "from_main":
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

                elif dep["type"] == "from_step":
                    src = dep["step_id"]

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
                        f"Invalid dependency type '{dep['type']}' "
                        f"in step '{step_id}' param '{param}'"
                    )

                if step_id not in graph[src]:
                    graph[src].add(step_id)
                    in_degree[step_id] += 1

        nodes = set(in_degree.keys())
        non_leaves = set(graph.keys())
        real_leaves = nodes - non_leaves

        if len(real_leaves) != 1:
            raise ValueError(
                f"Workflow must have exactly ONE leaf task, "
                f"found {len(real_leaves)}: {sorted(real_leaves)}"
            )

        in_degree[FINAL_STEP_ID] = 0

        for leaf in real_leaves:
            graph[leaf].add(FINAL_STEP_ID)
            in_degree[FINAL_STEP_ID] += 1

        return graph, in_degree

    def topological_sort(
        self,
    ) -> tuple[list[str], defaultdict[str, set[str]]]:
        graph, in_degree = self.build_dependency_graph()

        nodes = set(in_degree.keys())
        non_leaves = set(graph.keys())
        leaves = nodes - non_leaves

        if len(leaves) != 1:
            raise ValueError(
                f"Workflow must have exactly ONE leaf task, "
                f"found {len(leaves)}: {sorted(leaves)}"
            )

        queue = deque(node for node, degree in in_degree.items() if degree == 0)

        order: list[str] = []

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

        if order[-1] != FINAL_STEP_ID:
            raise AssertionError(f"{FINAL_STEP_ID} must be the last step, got {order}")

        return order, graph


def unwrap_annotated(annotation):
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        return args[0], list(args[1:])
    return annotation, []


def extract_dependency(
    annotation: Any,
) -> FromMainDependency | FromStepDependency | None:
    """
    Extract FromMain / FromStep metadata from Annotated types.
    """
    if annotation is None:
        return None

    _, metadata = unwrap_annotated(annotation)
    for item in metadata:
        if isinstance(item, (FromMain, FromStep)):
            return item.to_dict()

    return None
