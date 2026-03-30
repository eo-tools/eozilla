#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import panel as pn

pn.extension()


class ObjectWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """
    A widget that provides a UI that renders the views
    of an object's properties.

    Its value is a dummy for compatibility only.
    """

    def __init__(
        self,
        inner_widgets: list[pn.widgets.WidgetBase],
        # label: str | None = None,
        **params,
    ):
        super().__init__(**params)
        # self.label = label
        self.inner_widgets = inner_widgets

    def __panel__(self):
        items: list[Any]
        if self.name:
            items = [
                f"### {self.name}" if self.name else None,
                pn.layout.Divider(margin=(-16, 0, 0, 8)) if self.name else None,
                *self.inner_widgets,
            ]
        else:
            items = self.inner_widgets
        return pn.Column(*items)
