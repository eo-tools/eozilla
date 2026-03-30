#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import math

import panel as pn
import param

import cuiman.ui as cui
import cuiman.ui.vm as cvm
from gavicore.models import DataType
from gavicore.util.json import JsonDateCodec

from ...vm import ViewModel
from .extras.array import ArrayWidget
from .extras.bbox import BBoxEditor
from .extras.nullable import NullableWidget
from .extras.object import ObjectWidget
from .fields import PanelLayoutField, PanelWidgetField
from .util import ArrayTextConverter

_ARRAY_CONVERTERS: dict[DataType, ArrayTextConverter] = {
    DataType.boolean: ArrayTextConverter.Boolean(),
    DataType.integer: ArrayTextConverter.Integer(),
    DataType.number: ArrayTextConverter.Number(),
    DataType.string: ArrayTextConverter.String(),
}

# TODO: handle type="discriminator"
# TODO: handle type="anyOf"
# TODO: handle type="allOf"
# TODO: handle type="oneOf"


class PanelWidgetFieldFactory(cui.FieldFactoryBase):
    def get_nullable_score(self, meta: cui.FieldMeta) -> int:
        return 1

    def create_nullable_field(self, ctx: cui.FieldContext) -> cui.Field:
        non_nullable_meta = ctx.meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        view_model = ctx.vm.nullable(non_nullable_field.view_model)
        return PanelWidgetField(
            view_model,
            NullableWidget(
                name=ctx.name,
                value=ctx.initial_value,
                inner_widget=non_nullable_field.view,
            ),
        )

    def get_object_score(self, meta: cui.FieldMeta) -> int:
        return 1

    def create_object_field(self, ctx: cui.FieldContext) -> cui.Field:
        prop_fields = ctx.create_property_fields()
        view_models = {k: f.view_model for k, f in prop_fields.items()}
        view_model = ctx.vm.object(properties=view_models)
        views = [f.view for f in prop_fields.values()]
        # view = pn.Column(*views)
        # return PanelViewableField(view_model, view)
        view = ObjectWidget(name=view_model.meta.label, inner_widgets=views)
        return PanelWidgetField(view_model, view)

    def get_array_score(self, meta: cui.FieldMeta) -> int:
        if meta.item is None:
            return 0
        item_type = meta.item.schema_.type
        if item_type is None:
            return 0
        format_ = meta.schema_.format
        if format_ is not None and format_.lower() == "bbox":
            return 10
        array_converter = _ARRAY_CONVERTERS.get(item_type)
        if array_converter is not None:
            return 1
        return 0

    def create_array_field(self, ctx: cui.FieldContext) -> cui.Field:
        view_model = ctx.vm.array()

        assert ctx.meta.item is not None

        format_ = ctx.schema.format
        if format_ is not None and format_.lower() == "bbox":
            return PanelWidgetField(view_model, BBoxEditor())

        item_type = ctx.meta.item.schema_.type
        assert item_type is not None
        array_converter = _ARRAY_CONVERTERS.get(item_type)
        assert array_converter is not None

        # TODO: handle type="array" complex types or with widget="editor"
        # if view_model.meta.widget == "editor" or array_converter is None:
        #     item_editor = ctx.create_child_field(ctx.meta.item)
        #     view = ArrayEditor(
        #         value=view_model.value,
        #         item_editor=item_editor.view,
        #         name=view_model.meta.label,
        #         value_factory=ctx.meta.get_initial_value,
        #     )
        #     return PanelWidgetField(view_model, view=view)

        view = ArrayWidget(
            value=view_model.value,
            converter=array_converter,
            separator=view_model.meta.separator,
            label=view_model.meta.label,
            description=view_model.meta.description,
        )
        return PanelWidgetField(view_model, view)

    def get_string_score(self, meta: cui.FieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: cui.FieldContext) -> cui.Field:
        view_model = ctx.vm.primitive()
        value = view_model.value
        label = view_model.meta.label
        enum = view_model.meta.enum
        description = view_model.meta.description
        format_ = view_model.schema.format
        if format_ == "date":
            json_codec = JsonDateCodec()
            date = json_codec.from_json(value) or datetime.date.today()
            return PanelWidgetField(
                view_model,
                pn.widgets.DatePicker(name=label, value=date, description=description),
                json_codec=json_codec,
            )
        if enum is not None:
            # TODO: check widget == "radio"
            view = pn.widgets.Select(
                name=label,
                options=enum,
                value=value,
                description=description,
            )
        elif ctx.meta.widget == "textarea":
            view = pn.widgets.TextAreaInput(
                name=label, value=value, description=description
            )
        else:
            view = pn.widgets.TextInput(
                name=label, value=value, description=description
            )
        return PanelWidgetField(view_model, view)

    def get_integer_score(self, meta: cui.FieldMeta) -> int:
        return 1

    def get_number_score(self, meta: cui.FieldMeta) -> int:
        return 1

    def create_integer_field(self, ctx: cui.FieldContext) -> cui.Field:
        view_model = ctx.vm.primitive()
        return PanelWidgetField(
            view_model, self._create_numeric_view(view_model, is_int=True)
        )

    def create_number_field(self, ctx: cui.FieldContext) -> cui.Field:
        view_model = ctx.vm.primitive()
        return PanelWidgetField(view_model, self._create_numeric_view(view_model))

    @classmethod
    def _create_numeric_view(
        cls, view_model: ViewModel, *, is_int: bool | None = None
    ) -> pn.widgets.WidgetBase:
        value = view_model.value
        label = view_model.meta.label
        description = view_model.meta.description
        widget_hint = view_model.meta.widget
        minimum = view_model.meta.minimum
        maximum = view_model.meta.maximum
        enum = view_model.meta.enum

        if enum:
            # TODO: check widget == "radio"
            if widget_hint == "slider":
                return pn.widgets.DiscreteSlider(name=label, value=value, options=enum)
            if widget_hint in ("select", None):
                return pn.widgets.Select(name=label, value=value, options=enum)

        if (
            widget_hint == "slider"
            and isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum < maximum
        ):
            step: int | float = pow(10.0, int(math.log10(maximum - minimum)) - 1.0)
            if is_int:
                slider_cls = pn.widgets.IntSlider
                step = round(step)
            else:
                slider_cls = pn.widgets.FloatSlider
            return slider_cls(
                name=label,
                value=value,
                start=minimum,
                end=maximum,
                step=step,
            )

        if is_int:
            input_cls = pn.widgets.IntInput
        else:
            input_cls = pn.widgets.FloatInput
        return input_cls(name=label, value=value, description=description)

    def get_boolean_score(self, _meta: cui.FieldMeta) -> int:
        return 1

    def create_boolean_field(self, ctx: cui.FieldContext) -> cui.Field:
        view_model = ctx.vm.primitive()
        if view_model.meta.widget == "switch":
            view = pn.widgets.Switch(value=view_model.value, name=view_model.meta.label)
        else:
            view = pn.widgets.Checkbox(
                value=view_model.value, name=view_model.meta.label
            )
        return PanelWidgetField(view_model, view)


class PanelFieldGroupFactory(cui.FieldGroupFactory):
    def create_row_field(
        self,
        ctx: cui.FieldContext,
        view_model: cvm.ViewModel,
        children: list[param.Parameterized],
    ) -> cui.Field:
        return PanelLayoutField(view_model, pn.Row(*children))

    def create_column_field(
        self,
        ctx: cui.FieldContext,
        view_model: cvm.ViewModel,
        children: list[param.Parameterized],
    ) -> cui.Field:
        return PanelLayoutField(view_model, pn.Column(*children))
