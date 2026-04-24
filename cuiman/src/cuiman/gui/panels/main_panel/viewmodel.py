#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from typing import Callable, TypeAlias

import fsspec
import param

from cuiman.api.config import AdvancedInputPredicate
from cuiman.api.exceptions import ClientError
from cuiman.gui.panels.main_panel.settings import MainPanelSettings
from gavicore.models import (
    Format,
    InputDescription,
    JobInfo,
    JobResults,
    Output,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    TransmissionMode,
)
from gavicore.ui import Field, FieldFactoryRegistry, FieldMeta
from gavicore.ui.providers.panel import PanelField
from gavicore.util.ensure import ensure_condition
from gavicore.util.request import ExecutionRequest

GetProcessAction: TypeAlias = Callable[[str], ProcessDescription]
ExecuteProcessAction: TypeAlias = Callable[[str, ProcessRequest], JobInfo]
GetJobResultsAction: TypeAlias = Callable[[str], JobResults]


class MainPanelViewModel(param.Parameterized):
    # --- public state (observable)
    #
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

    # --- dependent state
    #
    has_advanced = param.Boolean(default=False)
    execute_disabled = param.Boolean(default=False)
    get_request_disabled = param.Boolean(default=False)

    # --- internal state
    #
    _process_cache = param.Dict(default={}, precedence=-1)

    def __init__(
        self,
        *,
        process_list: ProcessList,
        process_list_error: ClientError | None,
        accept_process,
        is_advanced_input: AdvancedInputPredicate,
        get_process: GetProcessAction,
        execute_process: ExecuteProcessAction,
        field_factory_registry: FieldFactoryRegistry[PanelField],
        **params,
    ):
        super().__init__(**params)

        self._get_process = get_process
        self._execute_process = execute_process
        self._is_advanced_input = is_advanced_input
        self._field_factory_registry = field_factory_registry
        self.settings = MainPanelSettings()

        self._request_cache: dict[str, ProcessRequest] = {}

        self.processes = [p for p in process_list.processes if accept_process(p)]
        self.error = process_list_error

    def select_process(
        self, process_id: str | None, cache_prev_request: bool = True
    ) -> None:
        # Maybe cache the current request so we can restore it if same
        # process ID is selected again
        prev_process_id = self.selected_process_id
        if (
            cache_prev_request
            and prev_process_id is not None
            and prev_process_id != process_id
            and self.inputs_field is not None
        ):
            self._request_cache[prev_process_id] = self.create_request()

        # Maybe save the process ID to select it if view.show() is called again
        if process_id is not None:
            self.settings.process_id = process_id

        self.selected_process_id = process_id

    @param.depends("selected_process_id", watch=True)
    def _update_process_description(self):
        process_id = self.selected_process_id
        if not process_id:
            self.process_description = None
            return
        try:
            process_description = self._load_process_description(process_id)
            self._set_process_description(process_description, None)
        except ClientError as error:
            self._set_process_description(None, error)

    @param.depends("process_description", watch=True)
    def _update_enablements(self):
        self.execute_disabled = self.process_description is None
        self.get_request_disabled = self.process_description is None

    @param.depends("process_description", "show_advanced", watch=True)
    def _update_inputs(self):
        process = self.process_description
        if process is None:
            self.inputs_field = None
            return

        assert isinstance(process, ProcessDescription)

        request = self._request_cache.get(process.id)
        if request is not None and request.inputs:
            request_dict = request.model_dump(
                mode="json", exclude_defaults=True, exclude_none=True
            )
            initial_inputs = request_dict.get("inputs", {})
        else:
            initial_inputs = {}

        # We should actually not filter based on inputs directly.
        # Instead, filter the field metadata properties which
        # has more options as the metadata has already
        # parsed special x-ui control properties.

        input_descriptions: dict[str, InputDescription] = process.inputs or {}
        # Get the advanced inputs.
        advanced_input_names = set(
            k
            for k, v in input_descriptions.items()
            if self._is_advanced_input(process, k, v)
        )
        self.has_advanced = len(advanced_input_names) > 0

        # Filter inputs by "show_advanced" flag and
        if self.has_advanced and not self.show_advanced:
            input_descriptions = {
                k: v
                for k, v in input_descriptions.items()
                if k not in advanced_input_names
            }

        # Recreate the input fields
        input_field_meta = FieldMeta.from_input_descriptions(
            input_descriptions, title=""
        )
        self.inputs_field = PanelField.from_meta(
            input_field_meta,
            initial_value=initial_inputs,
            field_factory_registry=self._field_factory_registry,
        )

        self.settings.show_advanced = self.show_advanced

    def create_request(self) -> ExecutionRequest:
        pid = self.selected_process_id
        process = self.process_description
        input_field = self.inputs_field

        assert pid is not None
        assert process is not None
        assert input_field is not None
        assert isinstance(input_field.view_model.value, dict)

        # noinspection PyTypeChecker
        return ExecutionRequest(
            process_id=pid,
            dotpath=True,
            inputs=input_field.view_model.value,
            outputs=self._default_outputs(process),
        )

    def execute(self):
        request = self.create_request()
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

    def get_initial_process_id(self) -> str | None:
        processes = self.processes or []
        if not processes:
            return None
        process_id = processes[0].id
        for p in processes:
            if p.id == self.settings.process_id:
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

    def _set_process_description(
        self, process_description: ProcessDescription | None, error: ClientError | None
    ) -> None:
        self.process_description = process_description
        self.error = error

    def _load_process_description(self, process_id: str) -> ProcessDescription:
        if process_id in self._process_cache:
            process_description = self._process_cache[process_id]
        else:
            try:
                self.loading = True
                process_description = self._get_process(process_id)
                self._process_cache[process_id] = process_description
            finally:
                self.loading = False
        assert isinstance(process_description, ProcessDescription)
        return process_description

    @property
    def num_outputs(self) -> int:
        process = self.process_description
        return len(process.outputs) if process and process.outputs else 0

    def load_process_request_file(
        self, fs: fsspec.AbstractFileSystem, path: str
    ) -> None:
        self.settings.last_path = path
        with fs.open(path, "r") as stream:
            request_dict = json.load(stream)
        ensure_condition(
            isinstance(request_dict, dict), "Request must be a valid JSON object"
        )
        # will raise, if request_dict is invalid
        request = ExecutionRequest(**request_dict)
        process_id = request.process_id

        # will cache, if process description can be loaded
        # will raise, if process description cannot be loaded
        self._load_process_description(process_id)

        # Put the request into cache so it can be picked up
        self._request_cache[process_id] = request
        # Pick up process request just saved in cache
        if self.selected_process_id != process_id:
            # Select new process ID to trigger
            self.select_process(process_id, cache_prev_request=True)
        else:
            # Reselect previously selected process, but don't cache,
            # as this would override our process request just loaded
            self.select_process(process_id, cache_prev_request=False)
            self._update_inputs()

    def store_process_request_file(
        self, fs: fsspec.AbstractFileSystem, path: str
    ) -> None:
        self.settings.last_path = path
        request = self.create_request()
        with fs.open(path, "w") as stream:
            json.dump(
                request.model_dump(mode="json", exclude_defaults=True),
                stream,
                indent=2,
            )
