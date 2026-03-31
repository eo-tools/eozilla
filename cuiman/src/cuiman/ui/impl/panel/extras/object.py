#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn

from ..util import get_header_items

pn.extension()


class ObjectWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """
    A widget that provides a UI that renders the views
    of an object's properties.
    """

    def __init__(
        self,
        inner_viewable: pn.viewable.Viewable,
        **params,
    ):
        super().__init__(**params)
        self.inner_viewable = inner_viewable

    def __panel__(self):
        if self.name:
            return pn.Column(
                *get_header_items(self.name),
                self.inner_viewable,
            )
        else:
            return self.inner_viewable
