#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn

pn.extension()


class ObjectWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """
    A widget that provides a UI that renders the views
    of an object's properties.

    Its value is a dummy for compatibility only.
    """

    def __init__(self, name: str, inner_widgets: list[pn.widgets.WidgetBase], **params):
        super().__init__(**params)
        self.name = name
        self._inner_widgets = inner_widgets

    def __panel__(self):
        return pn.Column(
            f"### {self.name}",
            pn.layout.Divider(margin=(0, 0, 0, 0)),
            *self._inner_widgets,
        )
