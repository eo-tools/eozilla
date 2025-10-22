#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, TypeAlias

import panel as pn
import param

from s2gos_client.api.exceptions import ClientError
from s2gos_common.models import (
    JobInfo,
    JobList,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from s2gos_common.process import ExecutionRequest

from .component.container import ComponentContainer
from .job_info_panel import JobInfoPanel
from .jobs_observer import JobsObserver

ExecuteProcessAction: TypeAlias = Callable[[str, ProcessRequest], JobInfo]
GetProcessAction: TypeAlias = Callable[[str], ProcessDescription]


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
    ):
        super().__init__()
        self._processes = process_list.processes
        self._process_list_error = process_list_error

        self._on_execute_process = on_execute_process
        self._on_get_process = on_get_process

        process_select_options = [p.id for p in process_list.processes]
        if process_select_options:
            process_id = process_select_options[0]
        else:
            process_id = None

        self._process_select = pn.widgets.Select(
            name="Process", options=process_select_options, value=process_id
        )
        self._process_select.param.watch(
            lambda e: self._on_process_id_changed(e.new), "value"
        )

        self._process_doc_markdown = pn.pane.Markdown("")
        process_panel = pn.Column(
            # pn.pane.Markdown("# Process"),
            self._process_select,
            self._process_doc_markdown,
        )

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

        self._on_process_id_changed(process_id)

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

    def _on_process_id_changed(self, process_id: str | None = None):
        process_description: ProcessDescription | None = None
        process_markdown: str | None = None
        if not process_id:
            process_markdown = "_No process selected._"
        else:
            if process_id in self._processes_dict:
                process_description = self._processes_dict[process_id]
            else:
                try:
                    process_description = self._on_get_process(process_id)
                    self._processes_dict[process_id] = process_description
                except ClientError as e:
                    # TODO: also show e.api_error.traceback, when user expands the message
                    process_description = None
                    process_markdown = f"**Error**: {e}: {e.api_error.detail}"
            if process_description:
                process_markdown = (
                    f"**{process_description.title}**\n\n"
                    f"{process_description.description}"
                )

        self._process_doc_markdown.object = process_markdown
        if not process_description:
            self._execute_button.disabled = True
            self._request_button.disabled = True
            self._component_container = None
            self._inputs_panel[:] = []
            self._outputs_panel[:] = []
        else:
            self._execute_button.disabled = False
            self._request_button.disabled = False
            self._component_container = ComponentContainer.from_input_descriptions(
                process_description.inputs or {}, {}
            )
            self._inputs_panel[:] = self._component_container.get_viewables()
            self._outputs_panel[:] = []

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
        )


# Register MainPanel as a virtual subclass of JobsObserver
JobsObserver.register(MainPanel)
