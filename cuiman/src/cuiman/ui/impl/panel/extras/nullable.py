#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn
import param


pn.extension()


class NullableWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """A widget that provides a UI for values that can be null."""

    value = param.Parameter(default=None, allow_None=True)

    def __init__(self, inner: pn.widgets.WidgetBase, **params):
        super().__init__(**params)

        if "value" not in inner.param:
            raise ValueError("inner must have a writable 'value' parameter")

        self._toggle = pn.widgets.Switch(
            name=inner.name,
            value=self.value is not None,
            styles={"margin-bottom": "0px"},
        )
        self._inner = inner
        try:
            self._inner.name = ""
        except TypeError:
            # For some widget-like elements we get:
            # TypeError: Constant parameter 'name' cannot be modified
            pass

        # --- init inner value if needed
        if self.value is not None:
            self._inner.value = self.value

        # --- sync toggle → value
        self._toggle.param.watch(self._on_toggle_change, "value")

        self._inner.param.watch(self._on_inner_change, "value")

        # --- sync external value → UI
        self.param.watch(self._on_value_change, "value")

        self._update_visibility()

    # --- reactions

    def _on_toggle_change(self, event):
        if event.new:
            # enable → take inner value
            self.value = self._inner.value
        else:
            # disable → null
            self.value = None

    def _on_inner_change(self, event):
        if self._toggle.value:
            self.value = event.new

    def _on_value_change(self, event):
        if event.new is None:
            self._toggle.value = False
        else:
            self._toggle.value = True
            self._inner.value = event.new

        self._update_visibility()

    def _update_visibility(self):
        self._inner.visible = self._toggle.value

    # --- Panel rendering hook
    def __panel__(self):
        return pn.Column(self._toggle, self._inner, styles={"gap": "0px"})
