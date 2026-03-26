#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn

import cuiman.ui as cui
import cuiman.ui.vm as cvm

from .json import JsonCodec, JsonIdentityCodec


class PanelViewableField(cui.FieldBase):
    """A view adapter."""

    def __init__(self, view_model: cvm.ViewModel, view: pn.viewable.Viewable):
        assert isinstance(self.view, pn.viewable.Viewable)
        super().__init__(view_model, view)

    @property
    def view(self) -> pn.viewable.Viewable:
        """The panel Viewable."""
        return self.view


class PanelWidgetField(cui.FieldBase):
    def __init__(
        self,
        view_model: cvm.ViewModel,
        view: pn.widgets.Widget,
        *,
        json_codec: JsonCodec | None = None,
    ):
        assert isinstance(self.view, pn.widgets.Widget)
        super().__init__(view_model, view)
        self.json_codec = json_codec or JsonIdentityCodec()

    @property
    def view(self) -> pn.widgets.Widget:
        """The panel Viewable."""
        return self.view

    def _bind(self):
        def observe_vm(_e):
            self.view.param.value = self.json_codec.from_json(self.view_model.value)

        def observe_view():
            self.view_model.value = self.json_codec.to_json(self.view.param.value)

        self.view_model.watch(observe_vm)
        self.view.param.watch(observe_view, "value")
