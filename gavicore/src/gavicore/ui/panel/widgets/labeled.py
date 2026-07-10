#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn
import param

from ._util import get_header_items

pn.extension()


class LabeledWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """
    A widget that provides a UI that will always render the
    given inner widget with a label given by the widget's name,
    if any. Used for widgets that doesn't support labels.
    """

    divider = param.Boolean(default=False)

    def __init__(
        self,
        inner_viewable: pn.reactive.Reactive,
        divider: bool = False,
        link: bool = False,
        **params,
    ):
        super().__init__(**params)
        self.divider = divider
        self.inner_viewable = inner_viewable
        if link:
            inner_viewable.link(self, value="value", bidirectional=True)

    def __panel__(self):
        if self.name:
            return pn.Column(
                *get_header_items(self.name, divider=self.divider),
                self.inner_viewable,
            )
        else:
            return self.inner_viewable
