#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Final

import panel as pn

from gavicore.models import Schema
from gavicore.ui import FieldBase, FieldFactoryRegistry, FieldGenerator, FieldMeta
from gavicore.ui.vm import ViewModel
from gavicore.util.ensure import ensure_type
from gavicore.util.json import JsonCodec, JsonIdentityCodec
from gavicore.util.undefined import Undefined


class PanelField(FieldBase[pn.widgets.WidgetBase]):
    """A panel widget-like field."""

    UNAVAILABLE_VIEW: Final = pn.widgets.ButtonIcon(
        icon="mood-annoyed-2", name="Missing Field", disabled=True
    )
    """The panel widget used to indicate that a view is missing."""

    def __init__(
        self,
        view_model: ViewModel,
        view: pn.widgets.WidgetBase,
        *,
        json_codec: JsonCodec | None = None,
    ):
        ensure_type("view", view, pn.widgets.WidgetBase)
        self._json_codec = json_codec or JsonIdentityCodec()
        super().__init__(view_model, view)

    @property
    def view(self) -> pn.widgets.WidgetBase:
        """The Panel widget-like viewable."""
        assert isinstance(self._view, pn.widgets.WidgetBase)
        return self._view

    def _bind(self):
        def observe_vm(_e):
            self.view.value = self._json_codec.from_json(self.view_model.value)

        def observe_view(_e):
            self.view_model.value = self._json_codec.to_json(self.view.value)

        self.view_model.watch(observe_vm)
        self.view.param.watch(observe_view, "value")

    @classmethod
    def from_schema(
        cls,
        name: str,
        schema: Schema,
        initial_value: Any | Undefined = Undefined.value,
        field_factory_registry: FieldFactoryRegistry["PanelField"] | None = None,
    ) -> "PanelField":
        return cls.from_meta(
            FieldMeta.from_schema(name, schema),
            initial_value=initial_value,
            field_factory_registry=field_factory_registry,
        )

    @classmethod
    def from_meta(
        cls,
        meta: FieldMeta,
        initial_value: Any | Undefined = Undefined.value,
        field_factory_registry: FieldFactoryRegistry["PanelField"] | None = None,
    ) -> "PanelField":
        if field_factory_registry is None:
            from .registry import PanelFieldFactoryRegistry

            field_factory_registry = PanelFieldFactoryRegistry.create_default()
        assert field_factory_registry is not None
        generator = FieldGenerator[PanelField, pn.widgets.WidgetBase](
            field_factory_registry
        )
        return generator.generate_field(meta, initial_value=initial_value)
