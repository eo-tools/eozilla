#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import re
from functools import cached_property
from typing import Annotated, Any, Literal, TypeAlias, Union

import pydantic

from gavicore.models import (
    DataType,
    InputDescription,
    OutputDescription,
    Schema,
)
from gavicore.util.ensure import ensure_condition

UI_KEYS = ["x-ui", "ui", "xUI", "xUi"]
UI_KEY_PREFIXES = [f"{k}:" for k in UI_KEYS] + [f"{k}-" for k in UI_KEYS]

FieldWidgetType: TypeAlias = Literal[
    "checkbox",
    "input",
    "password",
    "radiobutton",
    "radiogroup",
    "select",
    "slider",
    "switch",
    "textarea",
]
"""Selection of widget type hints."""


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
    property, if any, or the original property order.
    """

    type: Literal["column", "row"]  # we may add "grid" or others
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

    This class should not be instantiated from its constructor;
    instead, use one of the factory methods

    - [from_input_description][gavicore.ui.FieldMeta.from_input_description]
    - [from_input_descriptions][gavicore.ui.FieldMeta.from_input_descriptions]
    - [from_schema][gavicore.ui.FieldMeta.from_schema]
    """

    model_config = pydantic.ConfigDict(
        extra="allow",
        validate_assignment=True,
    )

    # --- required

    name: str
    """The name of the field. This is the name of the 
    corresponding process input/output or property name of object
    fields."""

    schema_: Schema = pydantic.Field(..., alias="schema")
    """The original schema from which this metadata was extracted."""

    # --- optional

    properties: dict[str, "FieldMeta"] | None = None
    """The metadata of object properties. Set if schema type is "object"."""

    items: "FieldMeta | None" = None
    """The metadata of array items. Set if schema type is "array"."""

    one_of: "list[FieldMeta] | None" = None
    """The metadata for a schema's "oneOf" element, if given."""

    any_of: "list[FieldMeta] | None" = None
    """The metadata for a schema's "anyOf" element, if given."""

    all_of: "list[FieldMeta] | None" = None
    """The metadata for a schema's "allOf" element, if given."""

    layout: FieldLayout | None = None
    """Hint to lay out the children of this field."""

    widget: FieldWidgetType | str | None = None
    """Hint for the type of widget to be used for this field."""

    title: str | None = None
    """The title of this field. 
    See also [label][gavicore.ui.FieldMeta.label]."""

    description: str | None = None
    """The description text for this field."""

    tooltip: str | None = None
    """A tooltip text for this field."""

    placeholder: str | None = None
    """A placeholder text for this field."""

    nullable_parent: bool | None = None
    """If `True`, the parent of this field is a nullable field."""

    group_name: str | None = None
    """The name of the group in which this field will occur. 
    See also [FieldGroup][gavicore.ui.FieldGroup]."""

    order: int | None = None
    """The order of this field in the group. 
    The order's value is used to compare it against other `order` values 
    when sorting multiple fields in ascending order. 
    See also [FieldGroup][gavicore.ui.FieldGroup]."""

    required: bool | None = None
    """Whether this field originates from a required process input 
    or object property."""

    password: bool | None = None
    """Whether this field is a password input field."""

    separator: (
        Annotated[str, pydantic.StringConstraints(min_length=1, max_length=1)] | None
    ) = None
    """The separator character used for separating array items 
    when for arrays edited as text."""

    advanced: bool | None = None
    """Whether this field is considered an advanced field."""

    level: Literal["common", "advanced"] | str | None = None
    """User level of a field. A UI may decide to hide advanced fields."""

    # Other properties with default values initialized from schema.
    # They may be overridden and will be used in the UI instead.
    minimum: int | float | None = None
    """Minimum numeric value as used for slider widgets."""

    maximum: int | float | None = None
    """Maximum numeric value as used for slider widgets."""

    step: int | float | None = None
    """Step size as used for slider widgets."""

    # TODO: rename into options
    enum: list[Any] | None = None
    """Enumeration used for the options of select widgets."""

    ref: str | None = None
    """Set from schema reference property '$ref'. 
    Since we resolve schemas, the original $ref value is kept 
    so we can still use it to evaluate a schema's discriminator 
    mappings.
    """

    @property
    def nullable(self) -> bool:
        """Whether this field is nullable."""
        return self.schema_.nullable is True

    @property
    def default(self) -> Any:
        """This field's default value."""
        return self.schema_.default

    @cached_property
    def label(self) -> str:
        """
        The label is the title if the title is provided, even if it is empty.
        Otherwise, a label is created from the name.
        """
        return self.title if (self.title is not None) else _make_label(self.name)

    @classmethod
    def from_input_description(
        cls,
        input_name: str,
        input_description: InputDescription,
    ) -> "FieldMeta":
        """
        Extract field metadata from the given input name and input description.
        """
        schema, required = _schema_from_input_description(input_name, input_description)
        return cls.from_schema(input_name, schema, required=required)

    @classmethod
    def from_input_descriptions(
        cls,
        input_descriptions: dict[str, InputDescription],
        *,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> "FieldMeta":
        """
        Extract a field metadata instance of type "object" from given input descriptions.
        """
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
            "title": title,
            "description": description,
        }
        return cls.from_schema(
            name or "inputs",
            Schema(**schema_dict),
            required=True if len(required_names) > 0 else None,
        )

    @classmethod
    def from_schema(
        cls,
        name: str,
        schema: Schema,
        *,
        required: bool | None = None,
    ) -> "FieldMeta":
        """Create field metadata from an OpenAPI Schema."""
        f = FieldMetaFactory(name, schema)
        return f.create_field_meta(name, schema, required=required)

    @classmethod
    def from_schemas(
        cls, name: str, *schemas: Schema, required: bool | None = None
    ) -> "FieldMeta":
        ensure_condition(len(schemas) > 0, "missing schemas to merge")
        if len(schemas) == 1:
            return cls.from_schema(name, schemas[0], required=required)

        data_type: Any | None = None
        merged_properties: dict[str, Any] | None = None
        merged_required: set[str] | None = None
        schema_dicts = [_make_schema_dict(s) for s in schemas]
        merged_schema_dict = {}
        for schema_dict in schema_dicts:
            if "type" in schema_dict:
                t = schema_dict["type"]
                if data_type is None:
                    data_type = t
            if "required" in schema_dict:
                r = schema_dict["required"]
                assert isinstance(r, list)
                if merged_required is None:
                    merged_required = set()
                merged_required.update(r)
            if "properties" in schema_dict:
                p = schema_dict["properties"]
                assert isinstance(p, dict)
                if merged_properties is None:
                    merged_properties = {}
                merged_properties.update(p)
            merged_schema_dict.update(schema_dict)
        if data_type is not None:
            merged_schema_dict["type"] = data_type
        if merged_properties is not None:
            merged_schema_dict["properties"] = merged_properties
        if merged_required is not None:
            merged_schema_dict["required"] = list(merged_required)
        return FieldMeta.from_schema(
            name,
            Schema(**merged_schema_dict),
            required=required,
        )

    @classmethod
    def from_field_metas(
        cls, name: str, *metas: "FieldMeta", required: bool | None = None
    ) -> "FieldMeta":
        ensure_condition(len(metas) > 0, "missing field metadata to merge")
        return cls.from_schemas(name, *(m.schema_ for m in metas), required=required)

    def to_non_nullable(self) -> "FieldMeta":
        """Create a non-nullable version of this field metadata."""
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


class FieldMetaFactory:
    def __init__(self, root_name: str, root_schema: Schema) -> None:
        self._root_name = root_name
        self._root_schema = root_schema
        self._resolved_metas: dict[str, FieldMeta] = {}

    def create_field_meta(
        self,
        name: str,
        schema: Schema,
        required: bool | None = None,
    ) -> FieldMeta:
        # create the field metadata stub first
        if schema.ref is not None:
            # is ref already resolved
            if schema.ref in self._resolved_metas:
                # Note that the returned field metadata may not be
                # fully populated with metadata, see below
                return self._resolved_metas[schema.ref]
            resolved_schema = self.resolve_schema_ref(schema.ref)
            meta = FieldMeta(
                name=name, schema=resolved_schema, ref=schema.ref, required=required
            )
            # We already register the field, although it is still a stub,
            # in order to detect cycles early
            self._resolved_metas[schema.ref] = meta
        else:
            meta = FieldMeta(name=name, schema=schema, required=required)
        # then update the stub with all the other metadata
        self._update_field_meta_from_schema(meta)
        return meta

    def _update_field_meta_from_schema(self, meta: FieldMeta) -> None:
        name = meta.name
        schema = meta.schema_
        ui_props = _extract_ui_props_from_schema(schema)
        required = ui_props.pop("required", meta.required)
        items: FieldMeta | None = None
        properties: dict[str, FieldMeta] | None = None
        if schema.type == DataType.array:
            schema_items = schema.items
            assert schema_items is None or isinstance(schema.items, Schema)
            items = self.create_field_meta(
                f"{name}_item",
                schema.items if isinstance(schema.items, Schema) else Schema(**{}),
                required=schema.minItems is not None and schema.minItems > 0,
            )
        elif schema.type == DataType.object:
            required_set = set(schema.required) if schema.required else set()
            properties = {}
            if schema.properties:
                for prop_name, prop_schema in schema.properties.items():
                    # noinspection PyTypeChecker
                    properties[prop_name] = self.create_field_meta(
                        prop_name, prop_schema, required=(prop_name in required_set)
                    )

        one_of = self._resolve_schemas(schema.oneOf, name_prefix="option_")
        any_of = self._resolve_schemas(schema.anyOf, name_prefix="option_")
        all_of = self._resolve_schemas(schema.allOf, name_prefix="part_")

        update = dict(
            required=required,
            properties=properties,
            items=items,
            one_of=one_of,
            any_of=any_of,
            all_of=all_of,
            **ui_props,
        )
        for k, v in update.items():
            setattr(meta, k, v)

    def resolve_schema_ref(self, ref: str) -> Schema:
        if not ref.startswith("#/"):
            raise NotImplementedError(
                "$refs must be document-relative (start with '#/')"
            )
        # Note, ref will likely be "#/$defs/<Schema>"
        # or "#/components/schemas/<Schema>".
        # We therefore expect the schema definitions in
        #   { "$defs": {"<Schema>": ...}}
        # or
        #   { "components": {"schemas": {"<Schema>": ...}}}
        # which are found in the model_extra dict of the root schema.
        path = ref[2:].split("/")
        extras = self._root_schema.model_extra
        assert isinstance(extras, dict)
        s: dict[str, Any] = extras
        name: str | None = None
        for i, name in enumerate(path):
            ensure_condition(
                name in s,
                f"invalid $ref value: {'/'.join(path[: i + 1])!r} does not exist",
            )
            s = s[name]
            ensure_condition(
                isinstance(s, dict),
                f"invalid $ref value: dict expected for {'/'.join(path[: i + 1])!r}, "
                f"but got {type(s).__name__}",
                exception_type=TypeError,
            )
        if name is not None and "title" not in s:
            s["title"] = name.title()
        return Schema(**s)

    def _resolve_schemas(
        self, schemas: list[Schema] | None, name_prefix: str
    ) -> list[FieldMeta] | None:
        if schemas is not None:
            assert isinstance(schemas, list)
            return [
                self.create_field_meta(f"{name_prefix}{i}", s)
                for i, s in enumerate(schemas)
            ]
        return None


_EXCL_SCHEMA_PROPERTY_NAMES = {"properties", "items", "required"}
_VALIDATION_META = FieldMeta(name="validation_meta", schema=Schema(**{}))


def _extract_ui_props_from_schema(
    schema: Schema,
) -> dict[str, Any]:
    schema_dict = _make_schema_dict(schema)
    ui_props: dict[str, Any] = {}
    # update properties in ui_dict by yet unset FieldMeta values
    _update_ui_props_from_schema_props(schema_dict, ui_props)
    # update properties in ui_dict from UI object with UI properties
    _update_ui_props_from_ui_object(schema_dict, UI_KEYS, ui_props)
    # update properties in ui_dict from values of prefixed UI properties
    _update_ui_props_from_prefixed_ui_keys(schema_dict, UI_KEY_PREFIXES, ui_props)
    # finally, select only valid properties from ui_dict
    return _select_valid_ui_props(ui_props)


def _update_ui_props_from_schema_props(
    source: dict[str, Any], ui_props: dict[str, Any]
) -> None:
    for name, value in source.items():
        if name not in _EXCL_SCHEMA_PROPERTY_NAMES and name in FieldMeta.model_fields:
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


def _select_valid_ui_props(ui_props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in ui_props.items() if _is_valid_ui_prop(k, v)}


def _is_valid_ui_prop(k, v) -> bool:
    try:
        setattr(_VALIDATION_META, k, v)
        return True
    except (TypeError, ValueError):
        return False


def _get_initial_value(meta: FieldMeta) -> Any:
    schema = meta.schema_
    if schema.default is not None:
        return schema.default
    if schema.enum and len(schema.enum) > 0:
        return schema.enum[0]
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
            if schema.format == "date":
                return datetime.date.today().isoformat()
            # create string of length min_length
            min_length = schema.minLength if schema.minLength is not None else 0
            return "+" * min_length
        case DataType.array:
            assert isinstance(meta.items, FieldMeta)
            # create array of length min_items
            min_items = schema.minItems if schema.minItems is not None else 0
            item_meta = meta.items
            return [_get_initial_value(item_meta) for _i in range(min_items)]
        case DataType.object:
            assert isinstance(meta.properties, dict)
            # Note, we may also consider minProperties, additionalProperties
            # create object with required properties
            required = set(schema.required or [])
            properties = meta.properties
            return {
                k: m.get_initial_value() for k, m in properties.items() if k in required
            }
        case _:
            # TODO: handle other cases here: oneOf, anyOf, allOf
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
