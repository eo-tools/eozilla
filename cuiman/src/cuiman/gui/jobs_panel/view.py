#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, TypeAlias

import panel as pn

from ..jobs_observer import JobsObserver
from .viewmodel import JobsPanelViewModel

JobAction: TypeAlias = Callable[[str], Any]


class JobsPanelView(pn.viewable.Viewer):
    def __init__(self, vm: JobsPanelViewModel):
        super().__init__()
        self.vm = vm

        self.table = pn.widgets.Tabulator(
            pn.bind(vm.dataframe),
            selectable=True,
            disabled=True,
        )
        self.table.param.watch(lambda e: vm.set_selection(e.new), "selection")

        self.view = pn.Column(
            self.table,
            pn.Row(
                pn.widgets.Button(
                    name="Cancel",
                    disabled=pn.bind(lambda: not vm.can_cancel()),
                    on_click=lambda _: vm.cancel_selected(),
                ),
                pn.widgets.Button(
                    name="Delete",
                    button_type="danger",
                    disabled=pn.bind(lambda: not vm.can_delete()),
                    on_click=lambda _: vm.delete_selected(),
                ),
                pn.widgets.Button(
                    name="Restart",
                    disabled=pn.bind(lambda: not vm.can_restart()),
                    on_click=lambda _: vm.restart_selected(),
                ),
                pn.widgets.Button(
                    name="Get Results",
                    disabled=pn.bind(lambda: not vm.can_get_results()),
                    on_click=lambda _: vm.get_results_for_selected(),
                ),
            ),
            pn.bind(lambda: vm.message),
        )

    def __panel__(self):
        return self.view


# Keep the same observer registration behavior
JobsObserver.register(JobsPanelView)
