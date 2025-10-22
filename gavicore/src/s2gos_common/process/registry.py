#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from collections.abc import Iterator, Mapping
from typing import Callable, Optional

import pydantic

from .process import Process


class ProcessRegistry(Mapping[str, Process]):
    """
    A registry for processes.

    Processes are Python functions with extra metadata.

    Represents a read-only mapping from process identifiers to
    [Process][s2gos_common.process.Process] instances.
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
        input_fields: Optional[dict[str, pydantic.fields.FieldInfo]] = None,
        output_fields: Optional[dict[str, pydantic.fields.FieldInfo]] = None,
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
            input_fields: Optional mapping from function argument names
                to [`pydantic.Field`](https://docs.pydantic.dev/latest/concepts/fields/)
                annotations. The preferred way is to annotate the arguments directly
                as described in [The Annotated Pattern](https://docs.pydantic.dev/latest/concepts/fields/#the-annotated-pattern).
            output_fields: Mapping from output names to
                [`pydantic.Field`](https://docs.pydantic.dev/latest/concepts/fields/)
                annotations. Required, if you have multiple outputs returned as a
                dictionary. In this case, output names are the keys of your returned
                dictionary.
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
                input_fields=input_fields,
                output_fields=output_fields,
                inputs_arg=inputs_arg,
            )
            self._processes[process.description.id] = process
            return fn

        if function is not None:
            return register_process(function)
        else:
            return register_process
