#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import functools
from collections.abc import Mapping
from copy import deepcopy
from typing import Callable, Optional

from pydantic.fields import FieldInfo

from gavicore.models import InputDescription, OutputDescription

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

    # noinspection PyShadowingBuiltins
    def main(
        self,
        function: Callable | None = None,
        /,
        *,
        id: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        inputs: Optional[dict[str, FieldInfo | InputDescription]] = None,
        outputs: Optional[dict[str, FieldInfo | OutputDescription]] = None,
        inputs_arg: str | bool = False,
    ) -> Callable[[Callable], Workflow] | Callable:
        """
        A decorator that can be applied to a user function in order to
        register it as a process in this registry.

        Note:

            - Use `main` decorator to express a process that comprises multiple steps
              that require a reference to the main entry point.

            - Use `process` decorator to express a process that has no steps,
              hence requires no reference to a main step.

        The decorator can be used with or without parameters.

        Args:
            function: The decorated function that is passed automatically since
                `process()` is a decorator function.
            id: Optional process identifier. Must be unique within the registry.
                If not provided, the fully qualified function name will be used.
            version: Optional version identifier. If not provided, `"0.0.0"`
                will be used.
            title: Optional, short process title.
            description: Optional, detailed description of the process. If not
                provided, the function's docstring, if any, will be used.
            inputs: Optional mapping from function argument names
                to [`pydantic.Field`](https://docs.pydantic.dev/latest/concepts/fields/)
                or [`InputDescription`][gavicore.models.InputDescription] instances.
                The preferred way is to annotate the arguments directly
                as described in [The Annotated Pattern](https://docs.pydantic.dev/latest/concepts/fields/#the-annotated-pattern).
                Use `InputDescription` instances to pass extra information that cannot
                be represented by a `pydantic.Field`, e.g., `additionalParameters` or `keywords`.
            outputs: Mapping from output names to
                [`pydantic.Field`](https://docs.pydantic.dev/latest/concepts/fields/)
                or [`OutputDescription`][gavicore.models.InputDescription] instances.
                Required, if you have multiple outputs returned as a
                dictionary. In this case, the function must return a typed `tuple` and
                output names refer to the items of the tuple in given order.
            inputs_arg: Specifies the use of an _inputs argument_. An inputs argument
                is a container for the actual process inputs. If specified, it must
                be the only function argument (besides an optional job context
                argument) and must be a subclass of `pydantic.BaseModel`.
                If `inputs_arg` is `True` the only argument will be the input argument,
                if `inputs_arg` is a `str` it must be the name of the only argument.
        """

        def register_workflow(fn: Callable) -> Workflow:
            # noinspection PyUnresolvedReferences
            f_name = f"{fn.__module__}:{fn.__qualname__}"
            workflow_id = id or f_name
            workflow = Workflow(
                fn,
                workflow_id=workflow_id,
                id=id,
                version=version,
                title=title,
                description=description,
                inputs=inputs,
                outputs=outputs,
                inputs_arg=inputs_arg,
            )
            self._workflows[workflow_id] = workflow
            return workflow

        if function is None:
            return register_workflow
        return register_workflow(function)

    # alias for main, when users need to define just process without any steps
    process = main

    # --- Internal API ---

    def get_workflow(self, workflow_id: str) -> Workflow:
        return self._workflows[workflow_id]

    def workflows(self) -> dict[str, Workflow]:
        return self._workflows
