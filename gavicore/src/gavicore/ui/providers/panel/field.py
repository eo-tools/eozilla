#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import panel as pn

import gavicore.ui as cui
import gavicore.ui.vm as cvm
from gavicore.models import InputDescription, Schema
from gavicore.ui import Field, FieldGenerator, FieldMeta
from gavicore.util.json import JsonCodec, JsonIdentityCodec
from gavicore.util.undefined import Undefined


class PanelField(cui.FieldBase):
    """A panel widget-like field."""

    def __init__(
        self,
        view_model: cvm.ViewModel,
        view: pn.widgets.WidgetBase,
        *,
        json_codec: JsonCodec | None = None,
    ):
        isinstance(view, pn.widgets.WidgetBase)
        self._json_codec = json_codec or JsonIdentityCodec()
        super().__init__(view_model, view)

    @property
    def view(self) -> pn.widgets.WidgetBase:
        """The Panel widget-like viewable."""
        isinstance(self._view, pn.widgets.WidgetBase)
        return self._view

    def _bind(self):
        def observe_vm(_e):
            self.view.value = self._json_codec.from_json(self.view_model.value)

        def observe_view(_e):
            self.view_model.value = self._json_codec.to_json(self.view.value)

        self.view_model.watch(observe_vm)
        self.view.param.watch(observe_view, "value")

    @classmethod
    def from_input_descriptions(
        cls,
        input_descriptions: dict[str, InputDescription],
        initial_value: Any | Undefined = Undefined.value,
    ) -> Field:
        return cls.from_meta(
            FieldMeta.from_input_descriptions(input_descriptions),
            initial_value=initial_value,
        )

    @classmethod
    def from_schema(
        cls,
        name: str,
        schema: Schema,
        initial_value: Any | Undefined = Undefined.value,
    ) -> Field:
        return cls.from_meta(
            FieldMeta.from_schema(name, schema), initial_value=initial_value
        )

    @classmethod
    def from_meta(
        cls,
        meta: FieldMeta,
        initial_value: Any | Undefined = Undefined.value,
    ) -> Field:
        from .factory import PanelFieldFactory

        generator = FieldGenerator()
        generator.register_field_factory(PanelFieldFactory())
        return generator.generate_field(meta, initial_value=initial_value)
