#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import functools
from collections.abc import Mapping
from copy import deepcopy
from typing import ItemsView, ValuesView

from .process import Process
from .workflow import Workflow


class WorkflowRegistry(Mapping[str, Workflow]):
    """
    A registry for workflows.

    Workflows are one or many Python functions with extra metadata that execute
    one after another by creating explicit dependencies and passing outputs to
    downstream steps as defined.

    Represents a read-only mapping from process identifiers to
    [Process][procodile.process.Process] instances.

    Internally, [Workflow][procodile.workflow.Workflow] instances are used for
    holding the required metadata for creating dependencies, passing outputs as
    inputs to downstream steps and execution.
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

    def __contains__(self, workflow_id: str) -> bool:
        return workflow_id in self._workflows

    @staticmethod
    @functools.lru_cache
    def _as_process(workflow: Workflow) -> Process:
        """This is the facade process object that is returned when the client wants
        to see what processes are available and is also used to run the actual
        workflow"""

        # Exactly one main is required
        if len(workflow.registry.main) != 1:
            raise ValueError(
                f"Workflow {workflow.id!r} must have exactly one main process"
            )

        main = next(iter(workflow.registry.main.values()))

        projected: Process = deepcopy(main)

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

    # --- Public API ---

    def get_or_create_workflow(self, id: str) -> Workflow:
        if id in self._workflows:
            return self._workflows[id]
        definition = Workflow(id)
        self._workflows[id] = definition
        return definition

    def get(self, workflow_id: str, default=None) -> Process | None:
        try:
            return self[workflow_id]
        except KeyError:
            return default

    def values(self) -> ValuesView[Process]:
        return ValuesView(self)

    def items(self) -> ItemsView[str, Process]:
        return ItemsView(self)

    # --- Internal API ---

    def get_workflow(self, workflow_id: str) -> Workflow:
        return self._workflows[workflow_id]

    def workflows(self) -> dict[str, Workflow]:
        return self._workflows
