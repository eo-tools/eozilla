#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pandas as pd
import panel as pn

from gavicore.models import JobInfo
from .viewmodel import JobsPanelViewModel
from ..jobs_observer import JobsObserver


class JobsPanel(pn.viewable.Viewer):
    def __init__(self, vm: JobsPanelViewModel):
        super().__init__()
        self.vm = vm

        self.table = self._new_tabulator()
        self.table.param.watch(self._on_selection, "selection")

        self.btn_cancel = pn.widgets.Button(
            name="Cancel",
            # tooltip="Cancels the selected job(s)",
            button_type="primary",
            on_click=self._cancel,
        )
        self.btn_delete = pn.widgets.Button(
            name="Delete",
            # tooltip="Deletes the selected job(s)",
            button_type="danger",
            on_click=self._delete,
        )
        self.btn_restart = pn.widgets.Button(
            name="Restart",
            # tooltip="Restarts the selected job(s)",
            button_type="primary",
            on_click=self._restart,
        )
        self.btn_results = pn.widgets.Button(
            name="Get Results",
            # tooltip="Gets the results from the selected job(s)",
            button_type="primary",
            on_click=self._results,
        )

        self.message = pn.pane.Markdown("")
        self.view = pn.Column(
            self.table,
            pn.Row(
                self.btn_cancel,
                self.btn_delete,
                self.btn_restart,
                self.btn_results,
            ),
            self.message,
        )

        self.refresh()

    def __panel__(self):
        return self.view

    # ---- bindings ----

    def refresh(self):
        self.table.value = _jobs_to_dataframe(self.vm.state.jobs)
        self.btn_cancel.disabled = not self.vm.can_cancel()
        self.btn_delete.disabled = not self.vm.can_delete()
        self.btn_restart.disabled = not self.vm.can_restart()
        self.btn_results.disabled = not self.vm.can_get_results()

    def _on_selection(self, _):
        self.vm.update_selection(self.table.selection)
        self.refresh()

    def _cancel(self, _):
        self._run(self.vm.on_cancel, "Cancelled")

    def _delete(self, _):
        self._run(self.vm.on_delete, "Deleted")

    def _restart(self, _):
        self._run(self.vm.on_restart, "Restarted")

    def _results(self, _):
        self._run(self.vm.on_get_results, "Stored results")

    def _run(self, action, ok):
        if not action:
            return
        msgs = self.vm.run_action(
            action,
            lambda job_id, _: f"✅ {ok} job `{job_id}`",
            "⚠️ Failed job `{job}`: {message}",
        )
        self.message.object = "  \n".join(msgs)
        self.refresh()

    @classmethod
    def _new_tabulator(cls) -> pn.widgets.Tabulator:
        dataframe = _jobs_to_dataframe([])

        tabulator = pn.widgets.Tabulator(
            dataframe,
            theme="default",
            width=600,
            height=300,
            layout="fit_data",
            show_index=False,
            editors={},  # No editing
            # selectable=False,
            disabled=True,
            configuration={
                "columns": [
                    {"title": "Process ID", "field": "process_id"},
                    {"title": "Job ID", "field": "job_id"},
                    {"title": "Status", "field": "status"},
                    {
                        "title": "Progress",
                        "field": "progress",
                        "formatter": "progress",
                        "formatterParams": {
                            "min": 0,
                            "max": 100,
                            "color": [
                                "#f00",
                                "#ffa500",
                                "#ff0",
                                "#0f0",
                            ],  # red → orange → yellow → green
                        },
                    },
                    {"title": "Message", "field": "message"},
                    {
                        "title": "  ",
                        "field": "action",
                        "hozAlign": "center",
                        "formatter": "plaintext",
                        "cellClick": True,  # Needed to enable cell-level events
                        "cssClass": "action-cell",  # We'll style this column
                    },
                ]
            },
        )

        return tabulator


# Register JobsPanel as a virtual subclass of JobsObserver
JobsObserver.register(JobsPanel)


def _jobs_to_dataframe(jobs: list[JobInfo]):
    return pd.DataFrame([_job_to_dataframe_row(job) for job in jobs])


def _job_to_dataframe_row(job: JobInfo):
    return {
        "process_id": job.processID,
        "job_id": job.jobID,
        "status": job.status.value,
        "progress": job.progress or 0,
        "message": job.message or "-",
    }
