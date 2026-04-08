#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import math
from typing import Any, Literal

import panel as pn

from gavicore.models import DataType
from gavicore.ui import FieldContext, FieldFactoryBase, FieldMeta
from gavicore.ui.vm import SelectiveViewModel, ViewModel
from gavicore.util.json import JsonDateCodec
from gavicore.util.text import ArrayTextConverter, TextConverter

from .field import PanelField
from .widgets.array import ArrayEditor, ArrayWidget
from .widgets.bbox import BBoxEditor
from .widgets.labeled import LabeledWidget
from .widgets.nullable import NullableWidget

_ARRAY_TEXT_CONVERTERS: dict[DataType, ArrayTextConverter] = {
    DataType.boolean: TextConverter.BooleanArray(),
    DataType.integer: TextConverter.IntegerArray(),
    DataType.number: TextConverter.NumberArray(),
    DataType.string: TextConverter.StringArray(),
}

# TODO: handle type="discriminator"


class PanelFieldFactory(FieldFactoryBase[PanelField]):
    def get_nullable_score(self, meta: FieldMeta) -> int:
        return 5

    def create_nullable_field(self, ctx: FieldContext) -> PanelField:
        non_nullable_meta = ctx.meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta, no_label=True)
        view_model = ctx.vm.nullable(non_nullable_field.view_model)
        return PanelField(
            view_model,
            NullableWidget(
                name=ctx.name,
                value=ctx.initial_value,
                inner_widget=non_nullable_field.view,
            ),
        )

    def get_boolean_score(self, _meta: FieldMeta) -> int:
        return 5

    def create_boolean_field(self, ctx: FieldContext) -> PanelField:
        view_model = ctx.vm.primitive()
        if view_model.meta.widget == "switch":
            view = pn.widgets.Switch(value=view_model.value, name=view_model.meta.label)
        else:
            view = pn.widgets.Checkbox(
                value=view_model.value, name=view_model.meta.label
            )
        return PanelField(view_model, view)

    def get_integer_score(self, meta: FieldMeta) -> int:
        return 5

    def get_number_score(self, meta: FieldMeta) -> int:
        return 5

    def create_integer_field(self, ctx: FieldContext) -> PanelField:
        view_model = ctx.vm.primitive()
        return PanelField(
            view_model,
            self._create_numeric_view(view_model, label=ctx.label, is_int=True),
        )

    def create_number_field(self, ctx: FieldContext) -> PanelField:
        view_model = ctx.vm.primitive()
        return PanelField(
            view_model, self._create_numeric_view(view_model, label=ctx.label)
        )

    @classmethod
    def _create_numeric_view(
        cls,
        view_model: ViewModel,
        *,
        is_int: bool | None = None,
        label: str | None = None,
    ) -> pn.widgets.WidgetBase:
        value = view_model.value
        description = view_model.meta.description
        widget_hint = view_model.meta.widget
        minimum = view_model.meta.minimum
        maximum = view_model.meta.maximum
        enum = view_model.meta.enum

        if enum:
            if widget_hint == "radio":
                return pn.widgets.RadioBoxGroup(name=label, value=value, options=enum)
            if widget_hint == "button":
                return pn.widgets.RadioButtonGroup(
                    name=label, value=value, options=enum
                )
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

    def get_string_score(self, meta: FieldMeta) -> int:
        return 5

    def create_string_field(self, ctx: FieldContext) -> PanelField:
        view_model = ctx.vm.primitive()
        value = view_model.value
        label = view_model.meta.label
        enum = view_model.meta.enum
        description = view_model.meta.description
        format_ = view_model.schema.format
        widget_hint = ctx.meta.widget
        if format_ == "date":
            json_codec = JsonDateCodec()
            date = json_codec.from_json(value) or datetime.date.today()
            return PanelField(
                view_model,
                pn.widgets.DatePicker(name=label, value=date, description=description),
                json_codec=json_codec,
            )
        if enum is not None:
            if widget_hint == "radio":
                view = pn.widgets.RadioBoxGroup(name=label, value=value, options=enum)
            elif widget_hint == "button":
                view = pn.widgets.RadioButtonGroup(
                    name=label, value=value, options=enum, description=description
                )
            else:
                view = pn.widgets.Select(
                    name=label, value=value, options=enum, description=description
                )
        elif widget_hint == "textarea":
            view = pn.widgets.TextAreaInput(
                name=label, value=value, description=description
            )
        else:
            view = pn.widgets.TextInput(
                name=label, value=value, description=description
            )
        return PanelField(view_model, view)

    def get_array_score(self, meta: FieldMeta) -> int:
        assert meta.items is not None
        item_type = meta.items.schema_.type
        if item_type is None:
            return 0
        format_ = meta.schema_.format
        if format_ is not None and format_.lower() == "bbox":
            return 10
        array_converter = _ARRAY_TEXT_CONVERTERS.get(item_type)
        if array_converter is not None:
            return 5
        return 0

    def create_array_field(self, ctx: FieldContext) -> PanelField:
        view_model = ctx.vm.array()
        assert ctx.meta.items is not None

        widget_hint = view_model.meta.widget

        format_ = ctx.schema.format
        if (format_ is not None and format_.lower() == "bbox") or widget_hint == "map":
            return PanelField(view_model, BBoxEditor())

        item_schema = ctx.meta.items.schema_
        item_type = item_schema.type
        item_format = item_schema.format
        assert item_type is not None
        array_converter = _ARRAY_TEXT_CONVERTERS.get(item_type)
        assert array_converter is not None

        if (
            array_converter is not None
            and widget_hint != "editor"
            and (widget_hint == "input" or item_format is None)
        ):
            view = ArrayWidget(
                value=view_model.value,
                array_converter=array_converter,
                separator=view_model.meta.separator,
                name=ctx.label,
                description=view_model.meta.description,
            )
        else:

            def create_item_editor(_index: int, value: Any) -> pn.widgets.WidgetBase:
                assert isinstance(ctx.meta.items, FieldMeta)
                ctx.meta.items.title = ""  # Supress label for items
                item_field = ctx.create_item_field()
                item_field.view_model.value = value
                return item_field.view

            view = ArrayEditor(
                name=ctx.label,
                value=view_model.value,
                item_editor_factory=create_item_editor,
                item_value_factory=ctx.meta.items.get_initial_value,
            )
        return PanelField(view_model, view)

    def get_object_score(self, meta: FieldMeta) -> int:
        return 5

    def create_object_field(self, ctx: FieldContext) -> PanelField:
        prop_fields = ctx.create_property_fields()
        view_models = {k: f.view_model for k, f in prop_fields.items()}
        view_model = ctx.vm.object(properties=view_models)
        if ctx.meta.layout is not None:
            inner_viewable = ctx.layout(
                _layout_views,  # type: ignore[arg-type]
                {k: f.view for k, f in prop_fields.items()},
            )
        else:
            inner_viewable = _layout_views(
                ctx,
                "column",
                [f.view for f in prop_fields.values()],  # type: ignore[arg-type]
            )
        return PanelField(
            view_model,
            LabeledWidget(inner_viewable, name=ctx.label, divider=True),
        )

    def get_one_of_score(self, meta: FieldMeta) -> int:
        return 5

    def create_one_of_field(self, ctx: FieldContext) -> PanelField:
        assert ctx.meta.one_of is not None
        return self._create_one_of_field(ctx, ctx.meta.one_of)

    def get_any_of_score(self, meta: FieldMeta) -> int:
        return 5

    def create_any_of_field(self, ctx: FieldContext) -> PanelField:
        assert ctx.meta.any_of is not None
        return self._create_one_of_field(ctx, ctx.meta.any_of)

    def _create_one_of_field(
        self, ctx: FieldContext, options: list[FieldMeta]
    ) -> PanelField:
        match len(options):
            case 0:
                return self.create_untyped_field(ctx)
            case 1:
                field = ctx.create_child_field(options[0])
                assert isinstance(field, PanelField)
                return field

        child_fields = [ctx.create_child_field(fm, no_label=True) for fm in options]
        view_model = SelectiveViewModel(
            ctx.meta,
            options=[f.view_model for f in child_fields],
        )

        tab_options = [(f.meta.label, f.view) for f in child_fields]
        tabs = pn.layout.Tabs(*tab_options)

        view_model.active_index = tabs.active

        def on_active_tab_change(_e):
            view_model.active_index = tabs.active

        tabs.param.watch(on_active_tab_change, "active")
        view = LabeledWidget(tabs, name=ctx.label)
        return PanelField(view_model, view)

    def get_all_of_score(self, meta: FieldMeta) -> int:
        return 5

    def create_all_of_field(self, ctx: FieldContext) -> PanelField:
        assert ctx.meta.all_of is not None
        combined_meta = FieldMeta.from_field_metas(
            ctx.meta.name, *ctx.meta.all_of, required=ctx.meta.required
        )
        child_field = ctx.create_child_field(combined_meta, no_label=True)
        return PanelField(
            child_field.view_model,
            LabeledWidget(child_field.view, name=ctx.label, divider=True),
        )

    def get_untyped_score(self, meta: FieldMeta) -> int:
        return 5

    def create_untyped_field(self, ctx: FieldContext) -> PanelField:
        json_editor = pn.widgets.JSONEditor(
            value=ctx.initial_value,
            width=300,
            mode="text",
            menu=False,
            search=False,
        )
        return PanelField(
            ctx.vm.any(),
            LabeledWidget(json_editor, name=ctx.label, divider=False),
        )


def _layout_views(
    _ctx: FieldContext,
    direction: Literal["row", "column"],
    views: list[pn.viewable.Viewable],
) -> pn.Row | pn.Column:
    if direction == "row":
        return pn.Row(*views)
    else:
        return pn.Column(*views)
