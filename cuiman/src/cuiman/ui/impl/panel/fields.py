#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn

import cuiman.ui as cui
import cuiman.ui.vm as cvm
from gavicore.util.json import JsonCodec, JsonIdentityCodec


class PanelViewableField(cui.FieldBase):
    """A panel viewable field."""

    def __init__(self, view_model: cvm.ViewModel, view: pn.viewable.Viewable):
        assert isinstance(view, pn.viewable.Viewable)
        super().__init__(view_model, view)

    @property
    def viewable(self) -> pn.viewable.Viewable:
        """The panel viewable."""
        return self._view


class PanelWidgetField(cui.FieldBase):
    """A panel widget field."""

    def __init__(
        self,
        view_model: cvm.ViewModel,
        view: pn.widgets.Widget,
        *,
        json_codec: JsonCodec | None = None,
    ):
        assert isinstance(view, pn.widgets.Widget)
        super().__init__(view_model, view)
        self.json_codec = json_codec or JsonIdentityCodec()

    @property
    def widget(self) -> pn.widgets.Widget:
        """The widget."""
        return self._view

    def _bind(self):
        def observe_vm(_e):
            self.widget.value = self.json_codec.from_json(self.view_model.value)

        def observe_view(_e):
            self.view_model.value = self.json_codec.to_json(self.widget.value)

        self.view_model.watch(observe_vm)
        self.widget.param.watch(observe_view, "value")
