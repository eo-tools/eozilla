#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, TypeAlias

import panel as pn
import param

from cuiman.api.config import InputPredicate, ProcessPredicate
from cuiman.api.exceptions import ClientError
from gavicore.models import (
    JobInfo,
    JobList,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
    Output,
    OutputDescription,
)
from gavicore.util.request import ExecutionRequest
from .component import JsonValue

from .component.container import ComponentContainer
from .job_info_panel import JobInfoPanel
from .jobs_observer import JobsObserver

ExecuteProcessAction: TypeAlias = Callable[[str, ProcessRequest], JobInfo]
GetProcessAction: TypeAlias = Callable[[str], ProcessDescription]


class MainPanelSettings:
    # Last selected process identifier
    process_id: str | None = None
    # Whether to show advanced input options
    show_advanced: bool = False


class MainPanel(pn.viewable.Viewer):
    # can be normal list
    _processes = param.List(default=[], doc="List of process summaries")
    # can be normal dict
    _processes_dict = param.Dict(default={}, doc="Dictionary of cached processes")

    def __init__(
        self,
        process_list: ProcessList,
        process_list_error: ClientError | None,
        on_get_process: GetProcessAction,
        on_execute_process: ExecuteProcessAction,
        accept_process: ProcessPredicate,
        accept_input: InputPredicate,
        show_advanced: bool | None = None,
    ):
        super().__init__()

        processes = [p for p in process_list.processes if accept_process(p)]

        self._processes = processes
        self._process_list_error = process_list_error
        self._on_execute_process = on_execute_process
        self._on_get_process = on_get_process
        self._client_error: ClientError | None = None
        self._accept_input = accept_input

        # --- _process_select
        process_select_options = {
            f"{p.title if p.title else 'No Title'}  (id={p.id})": p.id
            for p in processes
        }
        process_id = self._get_initial_process_id(processes)
        self._process_select = pn.widgets.Select(
            name="Process", options=process_select_options, value=process_id
        )
        self._process_select.param.watch(self._on_process_id_changed, "value")

        # --- _advanced_switch
        self._advanced_switch = pn.widgets.Switch(
            name="Show advanced inputs",
            value=(
                MainPanelSettings.show_advanced
                if show_advanced is None
                else show_advanced
            ),
            disabled=False,
        )
        self._advanced_switch.param.watch(self._on_advanced_switch_changed, "value")

        # --- _process_doc_markdown
        self._process_doc_markdown = pn.pane.Markdown("")
        process_panel = pn.Column(
            # pn.pane.Markdown("# Process"),
            self._process_select,
            self._process_doc_markdown,
            self._advanced_switch,
        )

        # --- Buttons
        self._execute_button = pn.widgets.Button(
            name="Execute",
            # tooltip="Executes the selected process with the current request",
            button_type="primary",
            on_click=self._on_execute_button_clicked,
            disabled=True,
        )
        self._open_button = pn.widgets.Button(
            name="Open",
            on_click=self._on_open_request_clicked,
            disabled=True,
        )
        self._save_button = pn.widgets.Button(
            name="Save",
            on_click=self._on_save_request_clicked,
            disabled=True,
        )
        self._save_as_button = pn.widgets.Button(
            name="Save As...",
            on_click=self._on_save_as_request_clicked,
            disabled=True,
        )
        self._request_button = pn.widgets.Button(
            name="Get Request",
            on_click=self._on_get_process_request,
            disabled=True,
        )

        action_panel = pn.Row(
            self._execute_button,
            self._open_button,
            self._save_button,
            self._save_as_button,
            self._request_button,
        )

        self._inputs_panel = pn.Column()
        self._outputs_panel = pn.Column()

        self._last_job_info: JobInfo | None = None
        self._job_info_panel = JobInfoPanel()

        self._view = pn.Column(
            process_panel,
            self._inputs_panel,
            self._outputs_panel,
            action_panel,
            self._job_info_panel,
        )

        self._component_container: ComponentContainer | None = None

        class EventMock:
            def __init__(self, new: Any):
                self.new = new

        self._on_process_id_changed(EventMock(process_id))

    def __panel__(self) -> pn.viewable.Viewable:
        return self._view

    def on_job_added(self, job_info: JobInfo):
        self._job_info_panel.on_job_added(job_info)

    def on_job_changed(self, job_info: JobInfo):
        self._job_info_panel.on_job_changed(job_info)

    def on_job_removed(self, job_info: JobInfo):
        self._job_info_panel.on_job_removed(job_info)

    def on_job_list_changed(self, job_list: JobList):
        pass

    def on_job_list_error(self, job_list: JobList):
        # TODO: render error
        pass

    @classmethod
    def _get_initial_process_id(cls, processes: list[ProcessSummary]) -> str | None:
        if not processes:
            return None
        # Try reusing MainPanelSettings.process_id
        for p in processes:
            if p.id == MainPanelSettings.process_id:
                return p.id
        # Fallback to first entry
        return processes[0].id

    def _on_process_id_changed(self, event: Any):
        MainPanelSettings.process_id = event.new
        # noinspection PyBroadException
        try:
            self.__on_process_id_changed()
        except Exception as e:
            print(f"ERROR: {e}")

    def __on_process_id_changed(self):
        process = self._get_or_fetch_process_description()
        self._update_process_description_markdown(process)
        self._update_action_panel(process)
        self._update_inputs_and_outputs(process)

    def _on_advanced_switch_changed(self, event: Any):
        MainPanelSettings.show_advanced = bool(event.new)
        # noinspection PyBroadException
        try:
            self.__on_advanced_switch_changed()
        except Exception as e:
            print(f"ERROR: {e}")

    def __on_advanced_switch_changed(self):
        process = self._get_or_fetch_process_description()
        self._update_inputs_and_outputs(process)

    def _update_process_description_markdown(self, process: ProcessDescription | None):
        if process is not None:
            if process and process.description:
                markdown_text = f"**Description:** {process.description}"
            else:
                markdown_text = "**Description:** _No description available._"
        else:
            if self._client_error is not None:
                e = self._client_error
                markdown_text = f"**Error**: {e}: {e.api_error.detail}"
            else:
                markdown_text = "_No process selected._"

        self._process_doc_markdown.object = markdown_text

    def _update_inputs_and_outputs(
        self, process_description: ProcessDescription | None
    ):
        if process_description is None:
            self._advanced_switch.disabled = True
            self._component_container = None
            self._inputs_panel[:] = []
            self._outputs_panel[:] = []
            return

        last_values: dict[str, JsonValue]
        if self._component_container is not None:
            last_values = self._component_container.get_json_values()
        else:
            last_values = {}

        inputs = process_description.inputs or {}
        has_advanced_inputs = any(
            hasattr(v, "level") and v.level == "advanced" for v in inputs.values()
        )
        if not has_advanced_inputs:
            filtered_inputs = inputs
        else:
            params = {
                "level": "advanced" if self._advanced_switch.value is True else "common"
            }
            # noinspection PyArgumentList
            filtered_inputs = {
                k: v
                for k, v in inputs.items()
                if self._accept_input(process_description, k, v, **params)
            }

        self._advanced_switch.disabled = not has_advanced_inputs
        self._component_container = ComponentContainer.from_input_descriptions(
            filtered_inputs,
            last_values,
        )

        if not self._component_container.is_empty:
            self._inputs_panel[:] = self._component_container.get_viewables()
        else:
            self._inputs_panel[:] = [pn.pane.Markdown("_No inputs available._")]

        self._outputs_panel[:] = self.create_outputs_ui(process_description)

    def create_outputs_ui(self, process_description: ProcessDescription) -> list:
        outputs = process_description.outputs or {}
        num_outputs = len(outputs)

        self._output_mode = pn.widgets.RadioButtonGroup(
            name="Output",
            options={
                "default": "Default (let server decide)",
                "selection": "Selected (if supported by the server)",
            },
            button_type="default",
            value="default",
            on_change=self._on_output_mode_change,
        )
        self._output_mode.disabled = num_outputs < 2

        return [self._output_mode] + [
            self._create_output_option(k, v) for k, v in outputs.items()
        ]

    def _create_output_option(
        self, key: str, output: OutputDescription
    ) -> pn.widgets.Checkbox:
        name: str = output.title or output.schema_.title or key

        def handle_change(arg):
            print("handle_change:", key, arg)

        return pn.widgets.Checkbox(
            name=output.title or output.schema_.title or name,
            value=True,
            on_change=handle_change,
        )

    def _on_output_mode_change(self, arg):
        print("_on_output_mode_change:", arg)

    def _update_action_panel(self, process: ProcessDescription | None):
        self._execute_button.disabled = process is None
        self._request_button.disabled = process is None

    def _get_or_fetch_process_description(
        self, process_id: str | None = None
    ) -> ProcessDescription | None:
        process_id = process_id or self._process_select.value
        if not process_id:
            return None
        if process_id in self._processes_dict:
            return self._processes_dict[process_id]
        try:
            process = self._on_get_process(process_id)
            self._processes_dict[process_id] = process
            self._client_error = None
        except ClientError as client_error:
            process = None
            self._client_error = client_error
        return process

    def _on_execute_button_clicked(self, _event: Any = None):
        execution_request = self._new_execution_request()
        try:
            self._execute_button.disabled = True
            job_info = self._on_execute_process(
                execution_request.process_id, execution_request.to_process_request()
            )
            self._job_info_panel.job_info = job_info
        except ClientError as e:
            self._job_info_panel.client_error = e
        finally:
            self._execute_button.disabled = False

    def _on_open_request_clicked(self, _event: Any = None):
        # TODO implement open request
        pass

    def _on_save_request_clicked(self, _event: Any = None):
        # TODO implement save request
        pass

    def _on_save_as_request_clicked(self, _event: Any = None):
        # TODO implement save request as
        pass

    def _on_get_process_request(self, _event: Any = None):
        # noinspection PyProtectedMember
        from IPython import get_ipython

        var_name = "_request"
        get_ipython().user_ns[var_name] = self._new_execution_request()

    def _update_buttons(self):
        # TODO implement action enablement
        pass

    def _new_execution_request(self) -> ExecutionRequest:
        process_id = self._process_select.value
        assert process_id is not None

        process_description = self._processes_dict.get(process_id)
        assert process_description is not None

        component_container = self._component_container
        assert component_container is not None

        return ExecutionRequest(
            process_id=process_id,
            dotpath=True,
            inputs=component_container.get_json_values(),
            outputs=self.get_default_outputs(process_description),
        )

    @staticmethod
    def get_default_outputs(
        process_description: ProcessDescription,
    ) -> dict[str, Output]:
        return {
            k: Output(
                **{
                    "format": {"mediaType": "application/json"},
                    "transmissionMode": "reference",
                }
            )
            for k, v in (process_description.outputs or {}).items()
        }


# Register MainPanel as a virtual subclass of JobsObserver
JobsObserver.register(MainPanel)
