#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn
import param


pn.extension()


class ObjectWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """
    A widget that provides a UI that renders the views
    of an object's properties.

    Its value is a dummy for compatibility only.
    """

    def __init__(self, name: str, properties: list[param.Parameterized], **params):
        super().__init__(**params)
        self.name = name
        self.properties = properties

    def __panel__(self):
        return pn.Column(
            f"### {self.name}",
            pn.layout.Divider(margin=(0, 0, 0, 0)),
            *self.properties,
        )
