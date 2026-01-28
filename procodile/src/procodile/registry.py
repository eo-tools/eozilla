#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import functools
from collections.abc import Mapping
from copy import deepcopy
from typing import Callable

from .process import Process
from .workflow import Workflow


class ProcessRegistry(Mapping[str, Process]):
    """
    A registry for processes.

    Processes are Python functions with extra metadata and can be extended
    to create `workflows` using `steps` decorator.

    A Workflow consists of one or more Python functions with metadata,
    designed to execute sequentially by resolving dependencies and
    passing outputs to downstream steps.

    This class provides a read-only mapping from unique identifiers to
    facade-like [Process][procodile.process.Process] instances. While the
    user interacts with these processes, the registry internally
    manages full [Workflow][procodile.workflow.Workflow] instances.

    The internal Workflow objects hold the source-of-truth metadata required
    for dependency resolution and execution, while the exposed Process
    objects serve as the public interface for client interaction.
    """

    def __init__(self):
        self._workflows: dict[str, Workflow] = {}

    # --- Overriding Mapping interface ---

    def __getitem__(self, workflow_id: str) -> Process:
        return self._as_process(self._workflows[workflow_id])

    def __iter__(self):
        return iter(self._workflows)

    def __len__(self) -> int:
        return len(self._workflows)

    @staticmethod
    @functools.lru_cache
    def _as_process(workflow: Workflow) -> Process:
        """This is the facade process object that is returned when the client wants
        to see what processes are available and is also used to run the actual
        workflow."""

        main = next(iter(workflow.registry.main.values()))

        projected: Process = deepcopy(main)

        # Steps exist -> last step defines outputs
        if workflow.registry.steps:
            order, _ = workflow.execution_order
            last_step_id = order[-2]  # because the step before that is the actual
            # user defined last step.
            last_step = workflow.registry.steps[last_step_id]["step"]
            projected.description.outputs = last_step.description.outputs

        # Update the function of the Process exposed to be `workflow.run` so
        # that it executes the main and the steps after that in order.
        projected.function = workflow.run

        return projected

    # --- Public API ---

    def main(
        self, fn: Callable | None = None, **kwargs
    ) -> Callable[[Callable], Workflow] | Callable:
        def _main(func: Callable) -> Workflow:
            workflow_id = kwargs.get("id", None)
            if workflow_id is None:
                workflow_id = f"{func.__module__}:{func.__qualname__}"
            workflow = Workflow(func, workflow_id, **kwargs)
            self._workflows[workflow_id] = workflow
            return workflow

        if fn is None:
            return _main
        return _main(fn)

    # --- Internal API ---

    def get_workflow(self, workflow_id: str) -> Workflow:
        return self._workflows[workflow_id]

    def workflows(self) -> dict[str, Workflow]:
        return self._workflows
