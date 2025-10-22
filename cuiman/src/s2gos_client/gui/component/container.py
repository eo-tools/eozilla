#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import warnings
from dataclasses import dataclass
from typing import Any, Callable, Literal, TypeAlias

import param

from s2gos_common.models import InputDescription, Schema

from .component import Component
from .impl import register_all
from .json import JsonSchemaDict, JsonValue
from .registry import ComponentFactoryRegistry

FailMode: TypeAlias = Literal["raise", "warn", "ignore"]


class ComponentContainer:
    registry = ComponentFactoryRegistry()

    @dataclass
    class Item:
        schema: JsonSchemaDict
        # TODO: check if we need value here
        value: JsonValue
        component: Component

    @classmethod
    def from_input_descriptions(
        cls,
        input_descriptions: dict[str, InputDescription],
        json_values: dict[str, JsonValue],
        fail_mode: FailMode = "warn",
    ) -> "ComponentContainer":
        schemas: dict[str, JsonSchemaDict] = {}
        for k, v in input_descriptions.items():
            schema = _get_schema_from_input_description(v)
            if schema is not None:
                schemas[k] = schema
            elif fail_mode != "ignore":
                msg = f"Failed getting usable JSON schema for input {k!r}"
                if fail_mode == "warn":
                    warnings.warn(msg)
                else:
                    raise ValueError(msg)

        return cls(schemas, json_values, fail_mode=fail_mode)

    def __init__(
        self,
        schemas: dict[str, JsonSchemaDict],
        json_values: dict[str, JsonValue],
        fail_mode: Literal["raise", "warn", "ignore"] = "warn",
    ):
        self._entries: dict[str, ComponentContainer.Item] = {}
        for name, schema in schemas.items():
            factory = self.registry.find_factory(schema)
            if factory is not None:
                value: JsonValue = json_values.get(name, schema.get("default"))
                title: str = schema.get("title") or _get_title_from_name(name)  # type: ignore[assignment]
                component = factory.create_component(value, title, schema)
                # TODO: check if we need this
                component.watch_value(self._get_on_value_changed(name, component))
                self._entries[name] = ComponentContainer.Item(schema, value, component)
            elif fail_mode != "ignore":
                msg = (
                    f"Failed creating component for input {name!r}"
                    f" with schema {schema!r}"
                )
                if fail_mode == "raise":
                    raise ValueError(msg)
                warnings.warn(msg)

    def get_json_values(self):
        """Get component values as JSON values."""
        return {
            name: entry.component.get_json_value()
            for name, entry in self._entries.items()
        }

    def set_json_values(self, json_values: dict[str, JsonValue]):
        """Set component values from JSON values."""
        return {
            name: entry.component.set_json_value(json_values[name])
            for name, entry in self._entries.items()
            if name in json_values
        }

    def get_components(self) -> list[Component]:
        return [entry.component for entry in self._entries.values()]

    def get_viewables(self) -> list[param.Parameterized]:
        return [entry.component.viewable for entry in self._entries.values()]

    def _get_on_value_changed(self, name: str, component: Component) -> Callable:
        def on_value_changed(event: Any):
            json_value = component.json_codec.to_json(event.new)
            self._entries[name].value = json_value

        return on_value_changed


register_all(ComponentContainer.registry)


def _get_title_from_name(name: str) -> str:
    return name.capitalize().replace("-", " ").replace("_", " ")


def _get_schema_from_input_description(
    input_description: InputDescription,
) -> JsonSchemaDict | None:
    v = input_description
    if not isinstance(v.schema_, Schema):
        return None
    schema = v.schema_.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True, by_alias=True
    )
    is_scalar = v.minOccurs in (0, 1) and v.maxOccurs in (None, 1)
    if not is_scalar:
        schema = {
            "type": "array",
            "items": schema,
            "minItems": (v.minOccurs if isinstance(v.minOccurs, int) else None),
            "maxItems": (v.maxOccurs if isinstance(v.maxOccurs, int) else None),
        }
    if v.title:
        schema["title"] = v.title
    if v.description:
        schema["description"] = v.description
    return schema
