#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, TypeAlias

import panel as pn

from .viewmodel import JobsPanelViewModel

JobAction: TypeAlias = Callable[[str], Any]


class JobsPanelView(pn.viewable.Viewer):
    def __init__(self, vm: JobsPanelViewModel):
        super().__init__()
        self.vm = vm

        self.table = _create_jobs_table(vm)
        self.table.param.watch(lambda e: vm.set_selection(e.new), "selection")

        self.view = pn.Column(
            self.table,
            pn.Row(
                pn.widgets.Button(
                    name="Cancel",
                    button_type="danger",
                    disabled=vm.param.cancel_disabled,
                    on_click=lambda _: vm.cancel_selected(),
                ),
                pn.widgets.Button(
                    name="Delete",
                    disabled=vm.param.delete_disabled,
                    on_click=lambda _: vm.delete_selected(),
                ),
                pn.widgets.Button(
                    name="Restart",
                    disabled=True,  # TODO: replace by the following line once implemented
                    # disabled=vm.param.restart_disabled,
                    on_click=lambda _: vm.restart_selected(),
                ),
                pn.widgets.Button(
                    name="Get Results",
                    disabled=vm.param.get_results_disabled,
                    on_click=lambda _: vm.get_results_for_selected(),
                ),
            ),
            vm.message,
        )

    def __panel__(self):
        return self.view


def _create_jobs_table(vm: JobsPanelViewModel):
    return pn.widgets.Tabulator(
        vm.dataframe,
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
