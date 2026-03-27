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
    def view(self) -> pn.viewable.Viewable:
        """The panel viewable."""
        isinstance(self._view, pn.viewable.Viewable)
        return self._view


class PanelWidgetField(cui.FieldBase):
    """A panel widget-like field."""

    def __init__(
        self,
        view_model: cvm.ViewModel,
        view: pn.widgets.WidgetBase,
        *,
        json_codec: JsonCodec | None = None,
    ):
        isinstance(view, pn.widgets.WidgetBase)
        super().__init__(view_model, view)
        self.json_codec = json_codec or JsonIdentityCodec()

    @property
    def view(self) -> pn.widgets.WidgetBase:
        """The panel widget-like."""
        isinstance(self._view, pn.widgets.WidgetBase)
        return self._view

    def _bind(self):
        def observe_vm(_e):
            self.view.value = self.json_codec.from_json(self.view_model.value)

        def observe_view(_e):
            self.view_model.value = self.json_codec.to_json(self.view.value)

        self.view_model.watch(observe_vm)
        self.view.param.watch(observe_view, "value")
