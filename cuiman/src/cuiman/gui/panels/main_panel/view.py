#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import panel as pn
import panel.layout

from cuiman.api.config import AdvancedInputPredicate, ProcessPredicate
from cuiman.api.exceptions import ClientError
from cuiman.gui.ipy_helper import IPyHelper
from cuiman.gui.jobs_observer import JobsObserver
from cuiman.gui.panels import JobInfoPanelView
from gavicore.models import (
    JobInfo,
    JobList,
    JobStatus,
    OutputDescription,
    ProcessDescription,
    ProcessList,
)
from gavicore.ui import FieldFactoryRegistry
from gavicore.ui.panel import PanelField

from ..util import FileOpenPanel, FileSavePanel, PanelHeader
from .viewmodel import (
    ExecuteProcessAction,
    GetJobResultsAction,
    GetProcessAction,
    MainPanelViewModel,
)


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

    Also consider: The view should never "drive" initial state.
        It should only reflect it from the view-model.
    """

    def __init__(
        self,
        process_list: ProcessList,
        process_list_error: ClientError | None,
        get_process: GetProcessAction,
        execute_process: ExecuteProcessAction,
        get_job_results: GetJobResultsAction,
        accept_process: ProcessPredicate,
        is_advanced_input: AdvancedInputPredicate,
        field_factory_registry: FieldFactoryRegistry[PanelField],
    ):
        super().__init__()

        self.vm = MainPanelViewModel(
            process_list=process_list,
            process_list_error=process_list_error,
            accept_process=accept_process,
            is_advanced_input=is_advanced_input,
            get_process=get_process,
            execute_process=execute_process,
            field_factory_registry=field_factory_registry,
        )
        # Used in view only, once we go async, move to viewmodel
        self._get_job_results = get_job_results

        process_select_options = {
            f"{p.title if p.title else 'No Title'}  (id={p.id})": p.id
            for p in self.vm.processes
        }
        self._process_select = pn.widgets.Select(
            # name="Process",
            options=process_select_options,
            value=pn.bind(lambda v: v, self.vm.param.selected_process_id),
        )

        self._advanced_switch = pn.widgets.Switch(
            value=pn.bind(lambda v: v, self.vm.param.show_advanced),
        )

        self._process_doc_markdown = pn.pane.Markdown("")
        self._message_markdown = pn.pane.Markdown("")

        def _on_file_menu_click(e):
            item = e.new
            if item == "load_request":
                self._load_request_dialog.panel.visible = True
            elif item == "store_request":
                self._store_request_dialog.panel.visible = True

        file_menu = pn.widgets.MenuButton(
            name="File Actions",
            items=[
                ("Load Request", "load_request"),
                ("Store Request", "store_request"),
            ],
            # width=120,
        )
        file_menu.on_click(_on_file_menu_click)

        self._load_request_dialog = FileOpenPanel(
            title="Load Process Request",
            path="./request.json",
            path_label="Process request file (JSON)",
            action_label="Load",
            action_callback=self.vm.load_process_request_file,
            level=4,
            indent=24,
        )

        self._store_request_dialog = FileSavePanel(
            title="Store Process Request",
            path="./request.json",
            path_label="Process request file (JSON)",
            action_label="Store",
            action_callback=self.vm.store_process_request_file,
            level=4,
            indent=24,
        )

        self._load_request_dialog.panel.visible = False
        self._store_request_dialog.panel.visible = False

        file_menu.disabled = pn.bind(
            lambda v1, v2: v1 or v2,
            self._load_request_dialog.panel.param.visible,
            self._store_request_dialog.panel.param.visible,
        )

        process_panel = pn.Column(
            PanelHeader(title="Process"),
            pn.layout.FlexBox(
                self._process_select,
                file_menu,
                align_content="space-between",
                align_items="flex-end",
            ),
            self._load_request_dialog,
            self._store_request_dialog,
            self._process_doc_markdown,
            pn.Row(
                self._advanced_switch,
                pn.widgets.StaticText(value="Show advanced inputs"),
                visible=pn.bind(lambda v: v, self.vm.param.has_advanced),
            ),
        )

        # --- Buttons
        self._execute_button = pn.widgets.Button(
            name="Execute",
            # tooltip="Executes the selected process with the current request",
            button_type="primary",
            on_click=self._on_execute_button_clicked,
            disabled=self.vm.param.execute_disabled,
            description="Execute the process using the current settings",
        )
        self._request_button = pn.widgets.Button(
            name="Get Request",
            on_click=self._on_get_process_request,
            disabled=self.vm.param.get_request_disabled,
            description=(
                "Sets the variable `_request` to the\ncurrent process request object"
            ),
        )
        self._results_button = pn.widgets.Button(
            name="Get Results",
            on_click=self._on_get_process_results,
            disabled=True,
            description=(
                "Sets the variable `_results` to the\ncurrent process results object"
            ),
        )

        action_panel = pn.Row(
            self._execute_button,
            self._request_button,
            self._results_button,
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

        # Watches View --> VM
        #
        self._process_select.param.watch(
            lambda e: self.vm.select_process(e.new), "value"
        )
        self._advanced_switch.param.watch(
            lambda e: setattr(self.vm, "show_advanced", e.new), "value"
        )

        # Watches VM --> View
        #
        self.vm.param.watch(self._update_process_description_ui, "process_description")
        self.vm.param.watch(self._update_process_inputs_ui, "inputs_field")
        self.vm.param.watch(self._update_process_outputs_ui, "process_description")
        self.vm.param.watch(
            lambda _: self._set_own_job_info(None), "selected_process_id"
        )

        # Reactive bindings
        #
        self._execute_button.disabled = pn.bind(
            lambda v: v, self.vm.param.execute_disabled
        )
        self._request_button.disabled = pn.bind(
            lambda v: v, self.vm.param.get_request_disabled
        )
        self._results_button.disabled = pn.bind(
            lambda job: job is None or job.status != JobStatus.successful,
            self._job_info_panel.param.job_info,
        )
        self._advanced_switch.visible = pn.bind(lambda v: v, self.vm.param.has_advanced)
        file_menu.disabled = pn.bind(
            lambda v1, v2: v1 or v2,
            self._load_request_dialog.panel.param.visible,
            self._store_request_dialog.panel.param.visible,
        )

        self.vm.select_process(self.vm.get_initial_process_id())

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

    def _update_process_description_ui(self, _event=None):
        process = self.vm.process_description
        if process is not None:
            if process and process.description:
                markdown_text = f"**Description:** {process.description}"
            else:
                markdown_text = "**Description:** _No description available._"
        else:
            error = self.vm.error
            if error is not None:
                markdown_text = f"**Error**: {error}: {error.api_error.detail}"
            else:
                markdown_text = "_No process selected._"
        self._process_doc_markdown.object = markdown_text

    def _update_process_inputs_ui(self, _event=None):
        process_description = self.vm.process_description
        if process_description is None:
            self._inputs_panel[:] = []
            return

        inputs_field = self.vm.inputs_field
        is_empty = (
            inputs_field is None
            or inputs_field.view is None
            or (
                isinstance(inputs_field.view, panel.layout.ListPanel)
                and len(inputs_field.view) == 0
            )
        )
        input_children: list[Any] = [PanelHeader(title="Inputs")]
        if is_empty:
            input_children.append(pn.pane.Markdown("_No inputs available._"))
        else:
            input_children.append(inputs_field.view)
        self._inputs_panel[:] = input_children

    def _update_process_outputs_ui(self, _event=None):
        process_description = self.vm.process_description
        if process_description is None:
            self._outputs_panel[:] = []
            return
        output_children: list[Any] = [PanelHeader(title="Outputs")]
        num_outputs = self.vm.num_outputs
        if num_outputs == 0:
            output_children.append("_No outputs available._")
        elif num_outputs == 1:
            output_children.append("_No selectable outputs available._")
        else:
            output_children.extend(self._create_outputs_ui(process_description))
        self._outputs_panel[:] = output_children

    def _create_outputs_ui(self, process_description: ProcessDescription) -> list[Any]:
        outputs = process_description.outputs or {}
        num_outputs = self.vm.num_outputs

        output_mode = pn.widgets.RadioButtonGroup(
            name="Output mode:",
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

        def enable_output_options(e):
            for v in output_options:
                v.disabled = e.new == "default"

        output_mode.param.watch(enable_output_options, "value")

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
            # TODO: request has changed - enable/disable elements
            print("_create_output_option:handle_change:", key, name, selected)

        checkbox = pn.widgets.Checkbox(
            name=output.title or output.schema_.title or name, value=True
        )
        checkbox.disabled = True
        checkbox.param.watch(lambda e: handle_change(e.new), "value")
        return checkbox

    def _on_execute_button_clicked(self, _event: Any = None):
        self._set_own_job_info(None)
        try:
            job_info = self.vm.execute()
            self._set_own_job_info(job_info)
        except ClientError as e:
            self._set_own_job_info(None, client_error=e)

    def _on_load_request_clicked(self, _event: Any = None):
        self._load_request_dialog.panel.open()

    def _on_store_request_clicked(self, _event: Any = None):
        self._store_request_dialog.panel.open()

    def _on_get_process_request(self, _event: Any = None):
        execution_request = self.vm.create_request()
        IPyHelper.set_execution_request_in_user_ns(execution_request)

    def _on_get_process_results(self, _event: Any = None):
        job_info = self._get_own_job_info()
        if job_info is None or job_info.status != JobStatus.successful:
            return
        try:
            job_results = self._get_job_results(job_info.jobID)
            IPyHelper.set_job_results_in_user_ns(job_results)
        except ClientError as e:
            self._set_own_job_info(job_info, e)

    def _get_own_job_info(self) -> JobInfo | None:
        return self._job_info_panel.job_info

    def _set_own_job_info(
        self, job_info: JobInfo | None, client_error: ClientError | None = None
    ) -> None:
        self._job_info_panel.job_info = job_info
        self._job_info_panel.client_error = client_error
