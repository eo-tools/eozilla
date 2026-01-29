#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import panel
import panel as pn
import param

from cuiman.api.exceptions import ClientError
from cuiman.gui.jobs_observer import JobsObserver
from gavicore.models import JobInfo, JobList


@JobsObserver.register  # virtual subclass, no runtime checks
class JobInfoPanelView(pn.viewable.Viewer):
    # Tha actual job info model
    job_info = param.ClassSelector(class_=JobInfo, allow_None=True, default=None)
    # This is an error that occurred when we couldn't retrieve job info
    client_error = param.ClassSelector(
        class_=ClientError, allow_None=True, default=None
    )

    def __init__(self, standalone: bool = False):
        super().__init__()
        self._standalone = standalone
        self._message_pane = panel.pane.Markdown()
        self._layout = pn.Column()
        self._render_layout()

    def __panel__(self) -> pn.viewable.Viewable:
        return self._layout

    # ---- JobsObserver interface implementation ----

    def on_job_added(self, job_info: JobInfo):
        self.on_job_changed(job_info)

    def on_job_changed(self, job_info: JobInfo):
        if self._is_observed_job(job_info):
            self.job_info = job_info
            self.client_error = None

    def on_job_removed(self, job_info: JobInfo):
        if self._is_observed_job(job_info):
            self._message_pane.object = (
                f"Job with ID=`{job_info.jobID}` has been deleted."
            )
            self.job_info = None
            self.client_error = None

    def on_job_list_changed(self, job_list: JobList):
        # Nothing to do
        pass

    def on_job_list_error(self, client_error: ClientError | None):
        self.client_error = client_error

    def _is_observed_job(self, job_info: JobInfo):
        return self.job_info is not None and self.job_info.jobID == job_info.jobID

    @param.depends("job_info", "client_error", watch=True)
    def _render_layout(self):
        if self.client_error is not None:
            self._layout.visible = True
            self._layout[:] = [pn.pane.Markdown(f"⚠️ **Error**: {self.client_error}")]
            return

        job_info: JobInfo = self.job_info
        if job_info is None:
            if self._standalone:
                self._layout.visible = True
                self._message_pane.object = "ℹ️ No job to display."
                self._layout.objects[:] = [self._message_pane]
            else:
                self._layout.visible = False
                self._layout.objects[:] = []
                self._message_pane.object = ""
            return
        else:
            self._layout.visible = True

        column1 = pn.Column(
            pn.widgets.StaticText(name="Process ID", value=job_info.processID),
            pn.widgets.StaticText(name="Job ID", value=job_info.jobID),
            pn.widgets.StaticText(name="Status", value=job_info.status),
            pn.widgets.StaticText(
                name="Progress", value=_to_value(job_info.progress, "%")
            ),
        )
        column2 = pn.Column(
            pn.widgets.StaticText(name="Created", value=_to_value(job_info.created)),
            pn.widgets.StaticText(name="Started", value=_to_value(job_info.started)),
            pn.widgets.StaticText(name="Updated", value=_to_value(job_info.updated)),
            pn.widgets.StaticText(name="Finished", value=_to_value(job_info.finished)),
        )
        self._message_pane.object = (
            f"**Message**: {job_info.message}" if job_info.message else ""
        )
        self._layout[:] = [self._message_pane, pn.Row(column1, column2)]
        # pn.state.notifications.success(f"Change {job_info.updated}", duration=1000)


def _to_value(value: Any, units: str = ""):
    return f"{value}{units}" if value is not None else "-"
