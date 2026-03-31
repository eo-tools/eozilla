#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, TypeAlias

import param

from cuiman.api.config import InputPredicate, ProcessPredicate
from cuiman.api.exceptions import ClientError
from gavicore.models import (
    Format,
    JobInfo,
    JobResults,
    Output,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
    TransmissionMode,
)
from gavicore.ui import Field, FieldMeta
from gavicore.ui.impl.panel import PanelField
from gavicore.util.json import JsonValue
from gavicore.util.request import ExecutionRequest

GetProcessAction: TypeAlias = Callable[[str], ProcessDescription]
ExecuteProcessAction: TypeAlias = Callable[[str, ProcessRequest], JobInfo]
GetJobResultsAction: TypeAlias = Callable[[str], JobResults]


class MainPanelViewModel(param.Parameterized):
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

    inputs_field = param.ClassSelector(
        class_=Field,
        default=None,
        allow_None=True,
    )

    last_job = param.ClassSelector(
        class_=JobInfo,
        default=None,
        allow_None=True,
    )

    # ----- dependent state

    has_advanced = param.Boolean(default=False)
    execute_disabled = param.Boolean(default=False)
    get_request_disabled = param.Boolean(default=False)

    # ----- internal state

    _process_cache = param.Dict(default={}, precedence=-1)

    # ----- construction

    def __init__(
        self,
        *,
        process_list: ProcessList,
        process_list_error: ClientError | None,
        accept_process: ProcessPredicate,
        accept_input: InputPredicate,
        get_process: GetProcessAction,
        execute_process: ExecuteProcessAction,
        **params,
    ):
        super().__init__(**params)

        self._get_process = get_process
        self._execute_process = execute_process
        self._accept_input = accept_input

        self.processes = [p for p in process_list.processes if accept_process(p)]
        self.error = process_list_error

        self.select_process(MainPanelViewModel._initial_process_id(self.processes))

    # ----- intent

    def select_process(self, process_id: str | None):
        if process_id:
            MainPanelViewModel.Settings.process_id = process_id
        self.selected_process_id = process_id
        self._load_process_description()
        self.execute_disabled = not process_id
        self.get_request_disabled = not process_id

    def update_inputs(self):
        process = self.process_description
        if process is None:
            self.inputs_field = None
            return

        last_values: dict[str, JsonValue]
        if self.inputs_field is not None and isinstance(
            self.inputs_field.view_model.value, dict
        ):
            last_values = self.inputs_field.view_model.value
        else:
            last_values = {}

        filtered_inputs = {
            k: v
            for k, v in (process.inputs or {}).items()
            if self._accept_input(process, k, v)
        }

        input_field_meta = FieldMeta.from_input_descriptions(filtered_inputs)
        if not self.show_advanced:
            input_field_meta = input_field_meta.filter(
                lambda m: not (m.advanced or m.level == "advanced"), skip_root=True
            )
        self.inputs_field = PanelField.from_meta(
            input_field_meta, initial_value=last_values
        )

        MainPanelViewModel.Settings.show_advanced = self.show_advanced

    def build_execution_request(self) -> ExecutionRequest:
        pid = self.selected_process_id
        process = self.process_description
        input_field = self.inputs_field

        assert pid is not None
        assert process is not None
        assert input_field is not None
        assert isinstance(input_field.view_model.value, dict)

        return ExecutionRequest(
            process_id=pid,
            dotpath=True,
            inputs=input_field.view_model.value,
            outputs=self._default_outputs(process),
        )

    def execute(self):
        request = self.build_execution_request()
        try:
            self.loading = True
            job = self._execute_process(
                request.process_id,
                request.to_process_request(),
            )
            self.last_job = job
            self.error = None
            return job
        except ClientError as e:
            self.error = e
            raise
        finally:
            self.loading = False

    # ----- helpers (state changing)

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
            process = self._get_process(pid)
            self._process_cache[pid] = process
            self.process_description = process
            self.error = None
        except ClientError as e:
            self.process_description = None
            self.error = e
        finally:
            self.loading = False

    # ----- helpers (pure)

    @staticmethod
    def _initial_process_id(
        processes: list[ProcessSummary],
    ) -> str | None:
        if not processes:
            return None
        process_id = processes[0].id
        for p in processes:
            if p.id == MainPanelViewModel.Settings.process_id:
                process_id = p.id
                break
        return process_id

    @staticmethod
    def _default_outputs(process):
        # noinspection PyArgumentList
        return {
            k: Output(
                format=Format(mediaType="application/json"),  # type: ignore[call-arg]
                transmissionMode=TransmissionMode.reference,
            )
            for k in (process.outputs or {}).keys()
        }

    class Settings:
        """Used to persist some view-model settings in memory."""

        # Last selected process identifier
        process_id: str | None = None
        # Whether to show advanced input options
        show_advanced: bool = False
