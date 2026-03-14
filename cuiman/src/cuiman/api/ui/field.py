#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from gavicore.models import (
    DataType,
    InputDescription,
    OutputDescription,
    Schema,
)

UI_KEYS = ["x-ui", "ui", "xUI", "xUi"]
UI_KEY_PREFIXES = [f"{k}:" for k in UI_KEYS]

UIFieldWidget: TypeAlias = Literal[
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


class UIFieldInfo(BaseModel):
    """Information used to generate a GUI field like a widget or panel.

    It has been collected from a process input/output description,
    the respective JSON schema, and from possible extension fields
    either contained in the descriptions or the JSON schemas.
    """

    model_config = ConfigDict(
        extra="allow",
    )

    # --- required

    name: str
    schema_: Schema = Field(..., alias="schema")

    # --- optional

    # If shema.type == "array" then this is a one-element list
    # with the first element describing the array items.
    # If shema.type == "object" then this is list of UI fields
    # of the object properties.
    children: list["UIFieldInfo"] | None = None
    widget: UIFieldWidget | str | None = None
    title: str | None = None
    description: str | None = None
    tooltip: str | None = None
    placeholder: str | None = None
    group: str | None = None
    order: int | str | None = None
    advanced: bool | None = None
    required: bool | None = None
    password: bool | None = None
    # For slider, the default to values from JSON schema
    minimum: int | float | None = None
    maximum: int | float | None = None

    @classmethod
    def from_input_description(
        cls,
        name: str,
        description: InputDescription,
    ) -> "UIFieldInfo":
        """Extract a UI-field from the input description."""
        return _ui_field_info_from_input_description(name, description)

    @classmethod
    def from_output_description(
        cls,
        name: str,
        description: OutputDescription,
    ) -> "UIFieldInfo":
        """Extract a UI-field from the output description."""
        return _ui_field_info_from_output_description(name, description)


def _ui_field_info_from_input_description(
    name: str,
    description: InputDescription,
) -> UIFieldInfo:
    min_occurs = 1 if description.minOccurs is None else description.minOccurs
    max_occurs = 1 if description.maxOccurs is None else description.maxOccurs

    if min_occurs > 1 or max_occurs == "unbounded" or max_occurs > 1:
        schema = Schema(
            type="array",
            items=description.schema_,
            minItems=min_occurs,
            maxItems=max_occurs if max_occurs != "unbounded" else None,
        )
        description = InputDescription(
            schema=schema, **_make_description_dict(description)
        )

    return _ui_field_info_from_description(name, description, required=min_occurs > 0)


def _ui_field_info_from_output_description(
    name: str,
    description: OutputDescription,
) -> UIFieldInfo:
    return _ui_field_info_from_description(name, description)


def _ui_field_info_from_description(
    name: str,
    description: InputDescription | OutputDescription,
    required: bool | None = None,
) -> UIFieldInfo:
    return _ui_field_info_from_schema(
        name=name,
        schema=description.schema_,
        overrides=_make_description_dict(description),
        required=required,
    )


def _ui_field_info_from_schema(
    name: str,
    schema: Schema,
    overrides: dict[str, Any] | None = None,
    required: bool | None = None,
) -> UIFieldInfo:
    schema_dict = _make_schema_dict(schema)
    ui_props = _extract_ui_props_from_sources(
        [schema_dict, overrides] if overrides else [schema_dict]
    )
    required = ui_props.pop("required", required)
    children = _ui_field_info_children_from_schema(name, schema)
    return UIFieldInfo(
        name=name, schema=schema, required=required, children=children, **ui_props
    )


def _ui_field_info_children_from_schema(
    name: str, schema: Schema
) -> list[UIFieldInfo] | None:
    if schema.type == DataType.array:
        item_name = f"{name}_item"
        if isinstance(schema.items, list):
            # Tuple of schemas:
            # Also JSON Schema allows for it, OpenAPI 3.0 explicitly does not.
            # We cover it here for the future.
            return [
                _ui_field_info_from_schema(f"{item_name}_{i}", s, required=True)
                for i, s in enumerate(schema.items)
            ]
        else:
            # "Normal" array with item type
            item_schema = (
                schema.items if isinstance(schema.items, Schema) else Schema(**{})
            )
            return [
                _ui_field_info_from_schema(
                    item_name,
                    item_schema,
                    required=schema.minItems is not None and schema.minItems > 0,
                )
            ]
    elif schema.type == DataType.object:
        required = set(schema.required) if schema.required else set()
        return [
            _ui_field_info_from_schema(
                prop_name, prop_schema, required=prop_name in required
            )
            for prop_name, prop_schema in (schema.properties or {}).items()
        ]
    return None


def _extract_ui_props_from_sources(
    sources: list[dict[Any, Any] | dict[str, Any] | Any],
) -> dict[str, Any]:
    ui_props: dict[str, Any] = {}
    for source in sources:
        # update properties in ui_dict by yet unset UIFieldInfo values
        _update_ui_props_from_field_props(source, ui_props)
        # update properties in ui_dict from UI object with UI properties
        _update_ui_props_from_ui_object(source, UI_KEYS, ui_props)
        # update properties in ui_dict from values of prefixed UI properties
        _update_ui_props_from_prefixed_ui_keys(source, UI_KEY_PREFIXES, ui_props)
    return ui_props


def _update_ui_props_from_field_props(
    source: dict[str, Any], ui_props: dict[str, Any]
) -> None:
    for field_name, field_info in UIFieldInfo.model_fields.items():
        if field_name in source:
            value = source[field_name]
            data_type = field_info.annotation
            # Note, the following guard prevents assigning values of
            # unexpected type (e.g. "required" of type bool vs. list[str])
            # This my become an issue if we start using non-primitive types.
            if data_type is not None and isinstance(value, data_type):
                ui_props[field_name] = value


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
        exclude={"schema", "schema_"},  # !
        exclude_none=True,
        exclude_defaults=True,
        exclude_unset=True,
    )
