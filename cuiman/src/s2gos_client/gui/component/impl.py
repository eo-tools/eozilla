#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import math
from typing import Any, Callable

import panel as pn

from .bbox import BboxSelector
from .component import Component, WidgetComponent
from .factory import ComponentFactoryBase
from .json import JsonDateCodec, JsonSchemaDict, JsonValue
from .registry import ComponentFactoryRegistry


class BooleanCF(ComponentFactoryBase):
    type = "boolean"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        value = value if value is not None else False
        return WidgetComponent(
            pn.widgets.Checkbox(name=title, value=value),
        )


class IntegerCF(ComponentFactoryBase):
    type = "integer"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        value = value if value is not None else 0
        assert isinstance(value, (int, float))
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum < maximum
        ):
            widget = pn.widgets.EditableIntSlider(
                name=title,
                start=int(minimum),
                end=int(maximum),
                value=int(value),
                step=max(1, pow(10, int(math.log10(maximum - minimum)) - 1) // 10),
            )
        else:
            widget = pn.widgets.IntInput(name=title, value=int(value))
        return WidgetComponent(widget)


class NumberCF(ComponentFactoryBase):
    type = "number"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        value = value if value is not None else 0
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and minimum < maximum
        ):
            widget = pn.widgets.EditableFloatSlider(
                name=title,
                start=minimum,
                end=maximum,
                value=value,
                step=pow(10.0, int(math.log10(maximum - minimum)) - 1.0),
            )
        else:
            widget = pn.widgets.FloatInput(name=title, value=value)
        return WidgetComponent(widget)


class StringCF(ComponentFactoryBase):
    type = "string"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        value = value or ""
        if "enum" in schema:
            widget = pn.widgets.Select(name=title, options=schema["enum"], value=value)
        else:
            widget = pn.widgets.TextInput(name=title, value=value)
        return WidgetComponent(widget)


class DateCF(ComponentFactoryBase):
    type = "string"
    format = "date"

    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        json_codec = JsonDateCodec()
        date = json_codec.from_json(value) or datetime.date.today()
        return WidgetComponent(
            pn.widgets.DatePicker(name=title, value=date), json_codec=json_codec
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


def register_all(registry: ComponentFactoryRegistry):
    BooleanCF.register_in(registry)
    IntegerCF.register_in(registry)
    NumberCF.register_in(registry)
    StringCF.register_in(registry)
    DateCF.register_in(registry)
    BboxCF.register_in(registry)
