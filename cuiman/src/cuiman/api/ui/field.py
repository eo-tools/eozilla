#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from gavicore.models import (
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
        frozen=True,
    )

    name: str
    schema_: Schema = Field(..., alias="schema")

    # optional values
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
    # How we deal with minOccurs/maxOccurs:
    #  1. If schema.type == "array" → multiplicity handled by JSON Schema.
    #  2. If schema is not array → minOccurs/maxOccurs determine repetition.
    #  3. minOccurs/maxOccurs missing → assume minOccurs=1, maxOccurs=1.

    ui_field_info = _ui_field_info_from_description(name, description)
    if ui_field_info.schema_.type == "array":
        # If schema.type == "array" we ignore minOccurs/maxOccurs
        return ui_field_info

    # Return modified field info w.r.t. minOccurs/maxOccurs
    return __ui_field_info_from_min_max_occurs(ui_field_info, description)


def __ui_field_info_from_min_max_occurs(
    ui_field_info: UIFieldInfo, description: InputDescription
):
    ui_field_info_dict = ui_field_info.model_dump(mode="python", by_alias=True)

    min_occurs = description.minOccurs
    max_occurs = description.maxOccurs

    if min_occurs is None:
        min_occurs = 1
    if max_occurs is None:
        max_occurs = 1

    if min_occurs > 1 or max_occurs == "unbounded" or max_occurs > 1:
        item_schema = description.schema_
        schema = Schema(
            type="array",
            items=item_schema,
            minItems=min_occurs,
            maxItems=max_occurs if max_occurs != "unbounded" else None,
        )
        ui_field_info_dict["schema"] = schema
        ui_field_info_dict["required"] = True
    else:
        ui_field_info_dict["required"] = min_occurs != 0

    return UIFieldInfo(**ui_field_info_dict)


def _ui_field_info_from_output_description(
    name: str,
    description: OutputDescription,
) -> UIFieldInfo:
    return _ui_field_info_from_description(name, description)


def _ui_field_info_from_description(
    name: str, description: InputDescription | OutputDescription
) -> UIFieldInfo:
    description_dict = description.model_dump(
        exclude_none=True,
        exclude_defaults=True,
        exclude_unset=True,
        by_alias=True,
    )
    schema_dict = description_dict.get("schema") or {}

    # later override earlier
    sources = [schema_dict, description_dict]
    ui_props: dict[str, Any] = {}
    for source in sources:
        # update properties in ui_dict by yet unset UIFieldInfo values
        _update_ui_props_from_field_props(source, ui_props)
        # update properties in ui_dict from UI object with UI properties
        _update_ui_props_from_ui_object(source, UI_KEYS, ui_props)
        # update properties in ui_dict from values of prefixed UI properties
        _update_ui_props_from_prefixed_ui_keys(source, UI_KEY_PREFIXES, ui_props)

    return UIFieldInfo(name=name, schema=description.schema_, **ui_props)


def _update_ui_props_from_field_props(
    source: dict[str, Any], ui_props: dict[str, Any]
) -> None:
    for field_name, _field_info in UIFieldInfo.model_fields.items():
        if field_name in source:
            ui_props[field_name] = source[field_name]


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
