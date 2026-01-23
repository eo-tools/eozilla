#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from collections import defaultdict, deque
from typing import Annotated, Any, Callable, Literal, TypedDict, get_args, get_origin

from .artifacts import ArtifactStore, ExecutionContext, NullArtifactStore
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


class WorkflowStepRegistry:
    """
    A registry for steps in a workflow.

    A *step* is a Python function annotated with either the `.main` or `.step`
    decorator and represents a unit of execution within a workflow.

    Internally, each step is a mapping from step identifiers to
    [Process][procodile.process.Process] instances.

    Each workflow **must define exactly one** `.main` step, which serves as the
    entry point. Defining more than one `.main` step will raise an error.

    In addition to the `.main` step, a workflow may define **zero or more**
    `.step` steps, which represent dependent or downstream processing stages.
    """

    def __init__(self):
        self.main: dict[str, Process] = {}
        self.steps: dict[str, StepEntry] = {}

    def register_main(self, fn: Callable, **kwargs) -> Callable:
        signature = inspect.signature(fn)
        outputs = WorkflowStepRegistry._extract_and_merge_outputs(signature, kwargs)

        if outputs:
            kwargs["outputs"] = outputs

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
                        f"Invalid dependency metadata for input '{name}': {value!r}"
                    )

        outputs = WorkflowStepRegistry._extract_and_merge_outputs(signature, kwargs)

        if outputs:
            kwargs["outputs"] = outputs

        step = Process.create(fn, **kwargs)
        self.steps[step.description.id] = {"step": step, "dependencies": dependencies}
        return fn

    @staticmethod
    def _extract_and_merge_outputs(
        signature: inspect.Signature,
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Extract outputs from Annotated return type or decorator kwargs."""

        return_type, return_metadata = unwrap_annotated(signature.return_annotation)

        outputs_from_annotation = None

        if return_metadata:
            assert len(return_metadata) == 1, (
                f"Only one return obj expected, got {len(return_metadata)}"
            )

            meta = return_metadata[0]
            if not isinstance(meta, dict):
                raise ValueError(
                    f"Invalid output metadata type, expected dict got: {type(meta)}"
                )
            outputs_from_annotation = meta

        outputs_from_kwargs = kwargs.pop("outputs", None)

        if outputs_from_kwargs:
            assert len(outputs_from_kwargs) == 1, (
                f"Only one object expected, got {len(return_metadata)}"
            )

            if not isinstance(outputs_from_kwargs, dict):
                raise ValueError(
                    f"Invalid output metadata type, expected dict got: {type(outputs_from_kwargs)}"
                )

        if outputs_from_annotation and outputs_from_kwargs:
            raise ValueError(
                "Outputs may be defined either in the return annotation "
                "or in the decorator, but not both."
            )

        return outputs_from_kwargs or outputs_from_annotation


class Workflow:
    """
    A workflow is a directed, acyclic composition of multiple steps (processes).

    Each workflow is exposed to users as a **single OGC API Process**, even though
    internally it consists of multiple dependent steps executed in sequence based
    on their defined dependencies.

    When a user requests execution of a workflow, the system orchestrates the
    execution of each step in the correct order. From the user's
    perspective, however, the workflow behaves exactly like an individual process.

    Each step within a workflow conforms to the OGC API – Processes (Part 3 draft)
    process model and is itself a process.
    """

    def __init__(self, id: str, artifact_store: ArtifactStore = NullArtifactStore()):
        self.id = id
        self.artifact_store = artifact_store

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
        lines = ["digraph pipeline {", "rankdir=LR;"]
        for node in deps:
            lines.append(f'"{node}";')
        for node, targets in deps.items():
            for t in targets:
                lines.append(f'"{node}" -> "{t}";')
        lines.append("}")
        return "\n".join(lines)

    def run(self, **function_kwargs):
        ctx = ExecutionContext(self.artifact_store)

        order, graph = self.execution_order
        # Run Main first
        main_id = next(iter(self.registry.main))
        main = self.registry.main[main_id]

        main_result = main.function(**function_kwargs)

        main_outputs = ctx.normalize_outputs(
            result=main_result,
            output_spec=main.description.outputs,
            store=self.artifact_store,
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
                    else:
                        raw = ctx.steps[dep["step_id"]][dep["output"]]

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
                store=self.artifact_store,
            )

            ctx.steps[step_id] = outputs

        return outputs

    @staticmethod
    def _collect_final_outputs(ctx: ExecutionContext, graph) -> dict[str, Any]:
        """
        Collect outputs from all immediate predecessors of FINAL_STEP_ID.
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

            if step_outputs is None or step_outputs == {}:
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
