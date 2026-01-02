#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from collections.abc import Iterator, Mapping
from typing import Callable, Optional

from pydantic.fields import FieldInfo

from gavicore.models import InputDescription, OutputDescription

from .process import Process


class ProcessRegistry(Mapping[str, Process]):
    """
    A registry for processes.

    Processes are Python functions with extra metadata.

    Represents a read-only mapping from process identifiers to
    [Process][procodile.process.Process] instances.
    """

    def __init__(self):
        self._processes: dict[str, Process] = {}

    def __getitem__(self, process_id: str, /) -> Process:
        return self._processes[process_id]

    def __len__(self) -> int:
        return len(self._processes)

    def __iter__(self) -> Iterator[str]:
        return iter(self._processes)

    # noinspection PyShadowingBuiltins
    def process(
        self,
        function: Optional[Callable] = None,
        /,
        *,
        id: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        inputs: Optional[dict[str, FieldInfo | InputDescription]] = None,
        outputs: Optional[dict[str, FieldInfo | OutputDescription]] = None,
        inputs_arg: str | bool = False,
    ) -> Callable[[Callable], Callable] | Callable:
        """
        A decorator that can be applied to a user function in order to
        register it as a process in this registry.

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

        def register_process(fn: Callable):
            process = Process.create(
                fn,
                id=id,
                version=version,
                title=title,
                description=description,
                inputs=inputs,
                outputs=outputs,
                inputs_arg=inputs_arg,
            )
            self._processes[process.description.id] = process
            return fn

        if function is not None:
            return register_process(function)
        else:
            return register_process

class FromMain:
    def __init__(self, name: str):
        self.name = name

    def to_dict(self):
        return {"step_id": "main", "output": self.name}

class FromStep:
    def __init__(self, step_id: str, output: str):
        self.step_id = step_id
        self.output = output

    def to_dict(self):
        return {"step_id": self.step_id, "output": self.output}


class WorkflowRegistry:
    def __init__(self):
        self._workflows: dict[str, "WorkflowDefinition"] = {}

    def __getitem__(self, workflow_id: str, /) -> "WorkflowDefinition":
        return self._workflows[workflow_id]

    def __len__(self) -> int:
        return len(self._workflows)

    def __iter__(self) -> Iterator[str]:
        return iter(self._workflows)

    def workflow(self, id: str) -> "WorkflowDefinition":
        definition = WorkflowDefinition()
        self._workflows[id] = definition
        return definition

class WorkflowDefinition:
    """A workflow is multiple steps connected to each other without any loops.

    Each step is basically a process as per current OGC Part 3 draft.
    """
    def __init__(self):
        self._main: dict[str, Process | dict] = {}
        self._steps: dict[str, Process | dict] = {}

    def main(self,
        function: Optional[Callable] = None,
        /,
        *,
        id: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        inputs: Optional[dict[str, FieldInfo | InputDescription]] = None,
        outputs: Optional[dict[str, FieldInfo | OutputDescription]] = None,
        inputs_arg: str | bool = False,
    ) -> Callable[[Callable], Callable] | Callable:
        def register_main(fn: Callable):
            main = Process.create(
                fn,
                id=id,
                version=version,
                title=title,
                description=description,
                inputs=inputs,
                outputs=outputs,
                inputs_arg=inputs_arg,
            )
            self._main[main.description.id] = main
            return fn

        if function is not None:
            return register_main(function)
        else:
            return register_main

    def step(self,
        function: Optional[Callable] = None,
        /,
        *,
        id: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        inputs: Optional[dict[str, FieldInfo | InputDescription | FromMain |
                                   FromStep]] = None,
        outputs: Optional[dict[str, FieldInfo | OutputDescription]] = None,
        inputs_arg: str | bool = False,
    ) -> Callable[[Callable], Callable] | Callable:
        def register_step(fn: Callable):
            schema_inputs = {}
            dependencies = {}
            for name, value in inputs.items():
                if isinstance(value, (FromMain, FromStep)):
                    dependencies[name] = value.to_dict()
                else:
                    schema_inputs[name] = value

            step = Process.create(
                fn,
                id=id,
                version=version,
                title=title,
                description=description,
                inputs=schema_inputs,
                outputs=outputs,
                inputs_arg=inputs_arg,
            )
            self._steps[step.description.id] = {
                                    "step": step,
                                    "dependencies": dependencies
                                }

            return fn

        if function is not None:
            return register_step(function)
        else:
            return register_step
