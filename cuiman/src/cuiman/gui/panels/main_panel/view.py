#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import panel as pn

from cuiman.api.config import AdvancedInputPredicate, ProcessPredicate
from cuiman.api.exceptions import ClientError
from cuiman.gui.jobs_observer import JobsObserver
from gavicore.models import (
    JobInfo,
    JobList,
    OutputDescription,
    ProcessDescription,
    ProcessList,
)

from ..job_info_panel import JobInfoPanelView
from .viewmodel import ExecuteProcessAction, GetProcessAction, MainPanelViewModel


@JobsObserver.register  # virtual subclass, no runtime checks
class MainPanelView(pn.viewable.Viewer):
    """
    The main panel GUI. Its design for allows the view
    (this class) & view-model (`MainViewModel` class) concept.

    The `MainPanel` (view) class is responsible for
        - widget creation,
        - layout,
        - rendering methods,
        - calls to view-model methods.

    If you attempt to enhance the main panel GUI, then consider that the
    following tasks probably belong into the `MainViewModel` class (view-model):
        - building domain objects
        - catching ClientError
        - touching data return by the API client

    Also consider: The view should never “drive” initial state.
        It should only reflect it from the view-model.
    """

    def __init__(
        self,
        process_list: ProcessList,
        process_list_error: ClientError | None,
        get_process: GetProcessAction,
        execute_process: ExecuteProcessAction,
        accept_process: ProcessPredicate,
        is_advanced_input: AdvancedInputPredicate,
    ):
        super().__init__()

        self.vm = MainPanelViewModel(
            process_list=process_list,
            process_list_error=process_list_error,
            accept_process=accept_process,
            is_advanced_input=is_advanced_input,
            get_process=get_process,
            execute_process=execute_process,
        )

        # --- _process_select
        process_select_options = {
            f"{p.title if p.title else 'No Title'}  (id={p.id})": p.id
            for p in self.vm.processes
        }
        self._process_select = pn.widgets.Select(
            name="Process",
            options=process_select_options,
            value=self.vm.selected_process_id,
        )

        def _on_select(e):
            self.vm.select_process(e.new)
            self._render_from_vm()

        self._process_select.param.watch(_on_select, "value")

        # --- _advanced_switch

        self._advanced_switch = pn.widgets.Switch(
            value=self.vm.show_advanced,
        )

        def _on_advanced(e):
            self.vm.show_advanced = bool(e.new)
            self.vm.update_inputs()
            self._render_inputs()

        self._advanced_switch.param.watch(_on_advanced, "value")

        # --- _process_doc_markdown

        self._process_doc_markdown = pn.pane.Markdown("")
        process_panel = pn.Column(
            # pn.pane.Markdown("# Process"),
            self._process_select,
            self._process_doc_markdown,
            pn.Row(
                self._advanced_switch,
                pn.widgets.StaticText(value="Show advanced inputs"),
                visible=self.vm.param.has_advanced,
            ),
        )

        # --- Buttons
        self._execute_button = pn.widgets.Button(
            name="Execute",
            # tooltip="Executes the selected process with the current request",
            button_type="primary",
            on_click=self._on_execute_button_clicked,
            disabled=self.vm.param.execute_disabled,
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
            disabled=self.vm.param.get_request_disabled,
        )

        action_panel = pn.Row(
            self._execute_button,
            self._open_button,
            self._save_button,
            self._save_as_button,
            self._request_button,
            margin=(10, 0, 0, 0),
        )

        self._inputs_panel = pn.Column()
        self._outputs_panel = pn.Column()

        self._job_info_panel = JobInfoPanelView(standalone=False)

        self._view = pn.Column(
            process_panel,
            self._inputs_panel,
            self._outputs_panel,
            action_panel,
            self._job_info_panel,
        )

        self._render_from_vm()

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

    def _render_from_vm(self):
        process = self.vm.process_description
        self._update_process_description_markdown(process)

        self.vm.update_inputs()
        self._render_inputs()
        self._render_outputs()

    def _update_process_description_markdown(self, process: ProcessDescription | None):
        # process = self._vm.process_description
        error = self.vm.error
        if process is not None:
            if process and process.description:
                markdown_text = f"**Description:** {process.description}"
            else:
                markdown_text = "**Description:** _No description available._"
        else:
            if error is not None:
                markdown_text = f"**Error**: {error}: {error.api_error.detail}"
            else:
                markdown_text = "_No process selected._"
        self._process_doc_markdown.object = markdown_text

    def _render_inputs(self):
        container = self.vm.input_container
        if container is None or container.is_empty:
            self._inputs_panel[:] = [pn.pane.Markdown("_No inputs available._")]
        else:
            self._inputs_panel[:] = container.get_viewables()

    def _render_outputs(self):
        process = self.vm.process_description
        num_outputs = self._num_outputs
        if process is None:
            self._outputs_panel[:] = []
        else:
            self._outputs_panel[:] = (
                self.create_outputs_ui(process) if num_outputs >= 2 else []
            )
        if num_outputs < 2:
            self._outputs_panel.visible = False

    def create_outputs_ui(self, process_description: ProcessDescription) -> list:
        outputs = process_description.outputs or {}
        num_outputs = self._num_outputs

        output_mode = pn.widgets.RadioButtonGroup(
            name="Output",
            options={
                "Default": "default",
                "Selected": "selection",
            },
            button_type="default",
            value="default",
        )
        output_mode.disabled = num_outputs < 2
        output_mode.description = (
            "As supported by the server, the default option is safest"
        )

        output_options = [self._create_output_option(k, v) for k, v in outputs.items()]

        def enable_output_options(value: str):
            for v in output_options:
                v.disabled = value == "default"

        pn.bind(enable_output_options, output_mode)

        return [
            output_mode,
            pn.Row(pn.pane.Markdown("Output options:"), *output_options),
        ]

    # noinspection PyMethodMayBeStatic
    def _create_output_option(
        self, key: str, output: OutputDescription
    ) -> pn.widgets.Checkbox:
        name: str = output.title or output.schema_.title or key

        def handle_change(selected: bool):
            # TODO
            print("_create_output_option:handle_change:", key, name, selected)

        checkbox = pn.widgets.Checkbox(
            name=output.title or output.schema_.title or name, value=True
        )
        checkbox.disabled = True
        pn.bind(handle_change, checkbox)
        return checkbox

    def _on_execute_button_clicked(self, _event: Any = None):
        try:
            job = self.vm.execute()
            self._job_info_panel.job_info = job
        except ClientError as e:
            self._job_info_panel.client_error = e

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
        get_ipython().user_ns[var_name] = self.vm.build_execution_request()

    @property
    def _num_outputs(self) -> int:
        process = self.vm.process_description
        return len(process.outputs) if process and process.outputs else 0
