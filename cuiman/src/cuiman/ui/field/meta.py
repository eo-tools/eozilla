#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import re
from functools import cached_property
from typing import Any, Literal, TypeAlias, Union

import pydantic

from gavicore.models import (
    DataType,
    InputDescription,
    OutputDescription,
    Schema,
)

UI_KEYS = ["x-ui", "ui", "xUI", "xUi"]
UI_KEY_PREFIXES = [f"{k}:" for k in UI_KEYS]

FieldWidgetType: TypeAlias = Literal[
    "checkbox",
    "password",
    "number",
    "text",
    "textarea",
    "radiobutton",
    "radiogroup",
    "select",
    "slider",
    "switch",
]


class FieldGroup(pydantic.BaseModel):
    """Definition of a group of complex UI fields.

    Example:

    ```python
    FieldGroup(
        type="row",
        items=[
            FieldGroup(type="column", items=["field_a", "field_b"]),
            FieldGroup(type="column", items=["field_c", "field_d"]),
        ]
    )
    ```

    Items can be other `Group` objects or the names of the
    fields that should be part of the layout. Another possibility
    for a field to join a layout is to set its `group_name` property
    to the target group's `name`.
    Children of a complex field whose names do not occur in any group
    of a layout tree and do not have the `group` property set
    will be appended to the root group of a layout tree.
    Their order will be determined by the value of the `order`
    property, if any, or the value of the `name` property.
    """

    type: Literal["column", "row"]
    items: list[Union["FieldGroup", str]] | None = None
    name: str | None = None
    title: str | None = None
    style: dict[str, Any] | None = None


FieldLayout: TypeAlias = FieldGroup | Literal["column", "row"]


class FieldMeta(pydantic.BaseModel):
    """Metadata used to generate a GUI field like a widget or panel.

    The properties of instances of this class have been collected
    from a process input/output description, the respective JSON schema,
    and from dedicated UI-related extension property values.

    For example, if a UI should use a dedicated enum value, it could be
    specified using the property named "x-ui:enum" or as a property "enum"
    in an object that is the value of the "x-ui" property.

    ```json
    {
        "schema": {"type": "number", "minimum": 0.1},
        "x-ui:enum": [0.1, 0.25, 0.5, 1.0]
    }
    ```

    or

    ```json
    {
        "schema": {"type": "number", "minimum": 0.1},
        "x-ui": {"enum": [0.1, 0.25, 0.5, 1.0]}
    }
    ```

    This class should not be instantiated from its constructor,
    instead, use one of the factory methods

    - [from_input_descriptions][from_input_descriptions]
    - [from_output_descriptions][from_output_descriptions]
    - [from_schema][from_schema]
    """

    model_config = pydantic.ConfigDict(
        extra="allow",
    )

    # --- required

    name: str
    schema_: Schema = pydantic.Field(..., alias="schema")

    # --- optional

    # If shema.type == "array" then this is a one-element list
    # with the first element describing the array items.
    # If shema.type == "object" then this is list of UI fields
    # of the object properties.
    # TODO: split into properties and
    #   properties: dict[str, FieldMeta] | None
    #   item: FieldMeta | None
    children: list["FieldMeta"] | None = None
    layout: FieldLayout | None = None
    widget: FieldWidgetType | str | None = None
    title: str | None = None
    description: str | None = None
    tooltip: str | None = None
    placeholder: str | None = None
    nullable_parent: bool | None = None
    group_name: str | None = None
    order: int | str | None = None
    advanced: bool | None = None
    required: bool | None = None
    password: bool | None = None
    # Other properties with default values initialized from schema.
    # They may be overridden and will be used in the UI instead.
    minimum: int | float | None = None
    maximum: int | float | None = None
    enum: list[Any] | None = None
    # default: Any | None = None
    # nullable: bool | None = None

    @property
    def properties(self) -> dict[str, "FieldMeta"]:
        assert self.schema_.type == DataType.object
        assert isinstance(self.children, list)
        return {v.name: v for v in self.children}

    @property
    def item(self) -> "FieldMeta":
        assert self.schema_.type == DataType.array
        assert isinstance(self.children, list) and len(self.children) == 1
        # noinspection PyTypeChecker
        return self.children[0]

    @property
    def nullable(self) -> bool:
        return self.schema_.nullable is True

    @property
    def default(self) -> Any:
        return self.schema_.default

    @cached_property
    def label(self) -> str:
        """
        The label is the title, if the title is provided.
        Otherwise, a label is created from the name.
        """
        return self.title or _make_label(self.name)

    @classmethod
    def from_input_descriptions(
        cls,
        input_descriptions: dict[str, InputDescription],
        name: str = "inputs",
        title: str | None = None,
        description: str | None = None,
    ) -> "FieldMeta":
        """Extract a UI-field from the input description."""
        properties = {}
        required_names = []
        for input_name, input_description in input_descriptions.items():
            schema, required = _schema_from_input_description(
                input_name, input_description
            )
            properties[input_name] = schema
            if required:
                required_names.append(input_name)

        schema_dict = {
            "type": "object",
            "properties": properties,
            "required": required_names or None,
            "title": title or _make_label(name),
            "description": description,
        }
        return cls.from_schema(
            name,
            Schema(**schema_dict),
            required=True if len(required_names) > 0 else None,
        )

    @classmethod
    def from_output_descriptions(
        cls,
        output_descriptions: dict[str, OutputDescription],
        name: str = "outputs",
        title: str | None = None,
        description: str | None = None,
    ) -> "FieldMeta":
        """Extract a UI-field from the input description."""
        properties = {
            output_name: _schema_from_output_description(
                output_name, output_description
            )
            for output_name, output_description in output_descriptions.items()
        }
        schema_dict = {
            "type": "object",
            "properties": properties,
            "title": title or _make_label(name),
            "description": description,
        }
        return cls.from_schema(name, Schema(**schema_dict))

    @classmethod
    def from_schema(
        cls,
        name: str,
        schema: Schema,
        required: bool | None = None,
    ) -> "FieldMeta":
        return _ui_field_meta_from_schema(name, schema, required=required)

    def to_non_nullable(self) -> "FieldMeta":
        if not self.schema_.nullable:
            return self
        new_schema = self.schema_.model_copy(update={"nullable": False})
        return self.model_copy(
            update={
                "schema_": new_schema,
                "nullable_parent": True,
            }
        )

    def get_initial_value(self) -> Any:
        """Compute an initial value for this UI field metadata."""
        return _get_initial_value(self)


def _schema_from_input_description(
    input_name: str,
    input_description: InputDescription,
) -> tuple[Schema, bool]:
    description_dict = _make_description_dict(input_description)
    min_occurs = description_dict.pop("minOccurs", None)
    max_occurs = description_dict.pop("maxOccurs", None)
    min_items = 1 if min_occurs is None else min_occurs
    max_items = (
        1 if max_occurs is None else (None if max_occurs == "unbounded" else max_occurs)
    )
    input_schema = input_description.schema_
    if min_items > 1 or max_items is None or max_items > 1:
        schema_dict = {
            "type": "array",
            "items": input_schema,
            "minItems": min_items,
            "maxItems": max_items,
        }
    else:
        schema_dict = _make_schema_dict(input_schema)
    schema_dict.update(description_dict)
    if "title" not in schema_dict:
        schema_dict["title"] = _make_label(input_name)
    return Schema(**schema_dict), min_items > 0


def _schema_from_output_description(
    output_name: str,
    output_description: OutputDescription,
) -> Schema:
    description_dict = _make_description_dict(output_description)
    schema_dict = _make_schema_dict(output_description.schema_)
    schema_dict.update(description_dict)
    if "title" not in schema_dict:
        schema_dict["title"] = _make_label(output_name)
    return Schema(**schema_dict)


def _ui_field_meta_from_schema(
    name: str,
    schema: Schema,
    required: bool | None = None,
) -> FieldMeta:
    schema_dict = _make_schema_dict(schema)
    ui_props = _extract_ui_props_from_schema_dict(schema_dict)
    required = ui_props.pop("required", required)
    children = _ui_field_meta_children_from_schema(name, schema)
    return FieldMeta(
        name=name, schema=schema, required=required, children=children, **ui_props
    )


def _ui_field_meta_children_from_schema(
    name: str, schema: Schema
) -> list[FieldMeta] | None:
    if schema.type == DataType.array:
        items = schema.items
        assert items is None or isinstance(items, Schema)
        item_name = f"{name}_item"
        item_schema = items if isinstance(items, Schema) else Schema(**{})
        # create one-element children array
        return [
            _ui_field_meta_from_schema(
                item_name,
                item_schema,
                required=schema.minItems is not None and schema.minItems > 0,
            )
        ]
    elif schema.type == DataType.object:
        required = set(schema.required) if schema.required else set()
        # create one-element children array
        return [
            _ui_field_meta_from_schema(
                prop_name, prop_schema, required=prop_name in required
            )
            for prop_name, prop_schema in (schema.properties or {}).items()
        ]
    return None


def _extract_ui_props_from_schema_dict(
    schema_dict: dict[str, Any],
) -> dict[str, Any]:
    ui_props: dict[str, Any] = {}
    # update properties in ui_dict by yet unset FieldMeta values
    _update_ui_props_from_field_props(schema_dict, ui_props)
    # update properties in ui_dict from UI object with UI properties
    _update_ui_props_from_ui_object(schema_dict, UI_KEYS, ui_props)
    # update properties in ui_dict from values of prefixed UI properties
    _update_ui_props_from_prefixed_ui_keys(schema_dict, UI_KEY_PREFIXES, ui_props)
    return ui_props


def _update_ui_props_from_field_props(
    source: dict[str, Any], ui_props: dict[str, Any]
) -> None:
    for name, meta in FieldMeta.model_fields.items():
        if name in source:
            value = source[name]
            data_type = meta.annotation
            # Note, the following guard prevents assigning values of
            # unexpected type (e.g. "required" of type bool vs. list[str])
            # This my become an issue if we start using non-primitive types.
            if data_type is not None and isinstance(value, data_type):
                ui_props[name] = value


def _update_ui_props_from_ui_object(
    source: dict[str, Any], ui_keys: list[str], ui_props: dict[str, Any]
) -> None:
    for k in ui_keys:
        v = source.get(k)
        if isinstance(v, dict):
            ui_props.update(v)


def _update_ui_props_from_prefixed_ui_keys(
    source: dict[str, Any], ui_key_prefixes: list[str], ui_props: dict[str, Any]
) -> None:
    def extract_extras(d: dict[str, Any], p: str) -> dict[str, Any]:
        return {k[len(p) :]: v for k, v in d.items() if k.startswith(p)}

    for prefix in ui_key_prefixes:
        extras = extract_extras(source, prefix)
        ui_props.update(extras)


def _get_initial_value(meta: FieldMeta) -> Any:
    schema = meta.schema_
    if schema.default is not None:
        return schema.default
    if schema.nullable:
        return None
    match schema.type:
        case DataType.boolean:
            return False
        case DataType.integer:
            return int(_get_initial_number(schema))
        case DataType.number:
            return float(_get_initial_number(schema))
        case DataType.string:
            min_length = schema.minLength if schema.minLength is not None else 0
            return "a" * min_length
        case DataType.array:
            min_items = schema.minItems if schema.minItems is not None else 0
            item_meta = meta.item
            return [_get_initial_value(item_meta) for _i in range(min_items)]
        case DataType.object:
            # TODO: consider minProperties, additionalProperties
            required = set(schema.required or [])
            properties = meta.properties
            return {
                k: m.get_initial_value() for k, m in properties.items() if k in required
            }
        case _:
            # TODO: handle other cases here: oneOf, anyOf, allOf, discriminator
            # raise ValueError(
            #     f"Unsupported untyped schema in field {meta.name!r}"
            # )
            return None


def _get_initial_number(schema: Schema) -> int | float:
    v: int | float = 0
    if schema.minimum is not None:
        v = min(v, schema.minimum)
    if schema.maximum is not None:
        v = min(v, schema.maximum)
    return v


def _make_schema_dict(schema: Schema | Literal[True] | None) -> dict[str, Any]:
    return (
        schema.model_dump(
            mode="python",
            exclude_none=True,
            exclude_defaults=True,
            exclude_unset=True,
        )
        if isinstance(schema, Schema)
        else {}
    )


def _make_description_dict(
    description: InputDescription | OutputDescription,
) -> dict[str, Any]:
    return description.model_dump(
        exclude={"schema_"},  # !
        exclude_none=True,
        exclude_defaults=True,
        exclude_unset=True,
    )


def _make_label(name: str) -> str:
    return " ".join(p.capitalize() for p in re.split(r"[_-]|(?<=[a-z])(?=[A-Z])", name))
