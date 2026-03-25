#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import math
from typing import Any, Callable

import panel as pn
import param

import cuiman.ui as cui
import cuiman.ui.vm as cvm

from .extras.bbox import BboxSelector
from .extras.nullable import NullableWidget
from .fields import PanelViewableField, PanelWidgetField
from .json import JsonDateCodec


def create_panel_ui_builder():
    builder = cui.UIFieldBuilder()
    builder.register_factory(PanelWidgetFieldFactory())
    builder.register_factory(PanelListPanelFactory())
    return builder


class PanelWidgetFieldFactory(cui.UIFieldFactoryBase):
    def get_object_score(self, ctx: cui.UIFieldContext) -> int:
        return 1

    def create_object_field(self, ctx: cui.UIFieldContext) -> cui.UIField:
        prop_fields = ctx.create_property_fields()
        view_models = {k: f.view_model for k, f in prop_fields.items()}
        view_model = ctx.vm.object(properties=view_models)
        views = [f.view for f in prop_fields.values()]
        view = pn.Column(*views, label=view_model.meta.title)
        return PanelViewableField(view_model, view=view)

    def get_array_score(self, ctx: cui.UIFieldContext) -> int:
        return 1

    def create_array_field(self, ctx: cui.UIFieldContext) -> cui.UIField:
        view_model = ctx.vm.array()
        view = ListEditor(value=view_model.value, label=view_model.meta.title)
        return PanelWidgetField(view_model, view=view)

    def get_string_score(self, meta: cui.UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: cui.UIFieldContext) -> cui.UIField:
        view_model = ctx.vm.primitive()
        value = view_model.value
        schema = view_model.schema
        label = view_model.meta.title
        description = view_model.meta.description
        format_ = view_model.schema.format
        if format_ == "date":
            json_codec = JsonDateCodec()
            date = json_codec.from_json(value) or datetime.date.today()
            return PanelWidgetField(
                view_model=view_model,
                view=pn.widgets.DatePicker(
                    name=label, value=date, description=description
                ),
                json_codec=json_codec,
            )
        if "enum" in schema:
            return PanelWidgetField(
                view_model,
                view=(
                    pn.widgets.Select(
                        name=label,
                        options=schema["enum"],
                        value=value,
                        description=description,
                    )
                ),
            )
        return PanelWidgetField(
            view_model,
            view=(
                pn.widgets.TextInput(name=label, value=value, description=description)
            ),
        )

    def get_number_score(self, meta: cui.UIFieldMeta) -> int:
        return 1

    def create_number_field(self, ctx: cui.UIFieldContext) -> cui.UIField:
        view_model = ctx.vm.primitive()
        view = NumberInput(value=view_model.value, label=view_model.meta.title)
        return PanelWidgetField(view_model, view=view)

    def get_boolean_score(self, _meta: cui.UIFieldMeta) -> int:
        return 1

    def create_boolean_field(self, ctx: cui.UIFieldContext) -> cui.UIField:
        view_model = ctx.vm.primitive()
        if view_model.meta.widget == "switch":
            view = pn.widgets.Switch(value=view_model.value, name=view_model.meta.title)
        else:
            view = pn.widgets.Checkbox(
                value=view_model.value, name=view_model.meta.title
            )
        return PanelWidgetField(view_model, view=view)

    def get_nullable_score(self, meta: cui.UIFieldMeta) -> int:
        return 1

    def create_nullable_field(self, ctx: cui.UIFieldContext) -> cui.UIField:
        non_nullable_meta = ctx.meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        non_nullable_view_model = non_nullable_field.view_model
        non_nullable_view = non_nullable_field.view
        view_model = ctx.vm.nullable(non_nullable=non_nullable_view_model)
        view = NullableWidget(
            value=ctx.initial_value,
            child=non_nullable_view,
            label=view_model.meta.title,
        )
        return PanelWidgetField(view_model, view=view)


class PanelListPanelFactory(cui.NestedObjectFactory):
    def create_row_field(
        self,
        ctx: cui.UIFieldContext,
        view_model: cvm.ViewModel,
        children: list[param.Parameterized],
    ) -> cui.UIField:
        return PanelViewableField(view_model=view_model, view=pn.Row(*children))

    def create_column_field(
        self,
        ctx: cui.UIFieldContext,
        view_model: cvm.ViewModel,
        children: list[param.Parameterized],
    ) -> cui.UIField:
        return PanelViewableField(view_model=view_model, view=pn.Column(*children))


# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------
# --------------------------------------------------------------------------------


class IntegerCF(ComponentFactoryBase):
    type = "integer"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        value = value if value is not None else 0
        assert isinstance(value, (int, float))
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        description = schema.get("description")
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum < maximum
        ):
            # EditableIntSlider does not support "description"
            widget = pn.widgets.EditableIntSlider(
                name=title,
                start=int(minimum),
                end=int(maximum),
                value=int(value),
                step=max(1, pow(10, int(math.log10(maximum - minimum)) - 1) // 10),
            )
        else:
            widget = pn.widgets.IntInput(
                name=title, value=int(value), description=description
            )
        return WidgetComponent(widget)


class NumberCF(ComponentFactoryBase):
    type = "number"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        value = value if value is not None else 0
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        description = schema.get("description")
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum < maximum
        ):
            # EditableFloatSlider does not support "description"
            widget = pn.widgets.EditableFloatSlider(
                name=title,
                start=minimum,
                end=maximum,
                value=value,
                step=pow(10.0, int(math.log10(maximum - minimum)) - 1.0),
            )
        else:
            widget = pn.widgets.FloatInput(
                name=title, value=value, description=description
            )
        return WidgetComponent(widget)


class DateCF(ComponentFactoryBase):
    type = "string"
    format = "date"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        json_codec = JsonDateCodec()
        date = json_codec.from_json(value) or datetime.date.today()
        description = schema.get("description")
        return WidgetComponent(
            pn.widgets.DatePicker(name=title, value=date, description=description),
            json_codec=json_codec,
        )


class BboxCF(ComponentFactoryBase):
    type = "array"
    format = "bbox"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        selector = BboxSelector()
        # TODO: set value & title
        return BboxComponent(selector)


class BboxComponent(Component):
    def __init__(self, bbox_selector: BboxSelector):
        super().__init__(bbox_selector)

    @property
    def bbox_selector(self) -> BboxSelector:
        # noinspection PyTypeChecker
        return self.viewable

    def get_value(self) -> Any:
        return self.bbox_selector.value

    def set_value(self, value: Any):
        self.bbox_selector.value = value

    def watch_value(self, callback: Callable[[Any], Any]):
        self.bbox_selector.param.watch(callback, "value")
