#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import param
from typing import Callable

from cuiman.api.exceptions import ClientError
from cuiman.gui.component import ComponentContainer, JsonValue
from gavicore.models import (
    ProcessList,
    ProcessDescription,
    ProcessSummary,
)

GetProcessAction = Callable[[str], ProcessDescription]


class MainViewModel(param.Parameterized):
    # ----- public state (observable)

    processes = param.List(default=[], doc="Filtered process summaries")
    selected_process_id = param.String(default=None, allow_None=True)

    process_description = param.ClassSelector(
        class_=ProcessDescription,
        default=None,
        allow_None=True,
    )

    loading = param.Boolean(default=False)
    error = param.ClassSelector(
        class_=ClientError,
        default=None,
        allow_None=True,
    )

    show_advanced = param.Boolean(default=False)

    input_container = param.ClassSelector(
        class_=ComponentContainer,
        default=None,
        allow_None=True,
    )

    # ----- internal state

    _process_cache = param.Dict(default={}, precedence=-1)

    # ----- construction

    def __init__(
        self,
        *,
        process_list: ProcessList,
        process_list_error: ClientError | None,
        accept_process,
        on_get_process: GetProcessAction,
        **params,
    ):
        super().__init__(**params)

        self._on_get_process = on_get_process

        self.processes = [p for p in process_list.processes if accept_process(p)]
        self.error = process_list_error

        self.selected_process_id = MainViewModel._initial_process_id(self.processes)

    # ----- intent

    def select_process(self, process_id: str | None):
        self.selected_process_id = process_id
        self._load_process_description()

    def _load_process_description(self):
        pid = self.selected_process_id
        if not pid:
            self.process_description = None
            return

        if pid in self._process_cache:
            self.process_description = self._process_cache[pid]
            self.error = None
            return

        try:
            self.loading = True
            process = self._on_get_process(pid)
            self._process_cache[pid] = process
            self.process_description = process
            self.error = None
        except ClientError as e:
            self.process_description = None
            self.error = e
        finally:
            self.loading = False

    def update_inputs(self, accept_input: Callable):
        process = self.process_description
        if process is None:
            self.input_container = None
            return

        last_values: dict[str, JsonValue] = (
            self.input_container.get_json_values()
            if self.input_container is not None
            else {}
        )

        inputs = process.inputs or {}

        has_advanced = any(
            hasattr(v, "level") and v.level == "advanced" for v in inputs.values()
        )

        if not has_advanced:
            filtered = inputs
        else:
            params = {"level": "advanced" if self.show_advanced else "common"}
            filtered = {
                k: v for k, v in inputs.items() if accept_input(process, k, v, **params)
            }

        self.input_container = ComponentContainer.from_input_descriptions(
            filtered,
            last_values,
        )

    # ----- helpers (pure)

    @staticmethod
    def _initial_process_id(
        processes: list[ProcessSummary],
    ) -> str | None:
        if not processes:
            return None
        return processes[0].id
