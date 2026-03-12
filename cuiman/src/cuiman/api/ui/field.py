#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Literal, TypeAlias

import pydantic
from pydantic import ConfigDict

from gavicore.models import DescriptionType, InputDescription, OutputDescription

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


class UIFieldInfo(pydantic.BaseModel):
    """Information used to generate a GUI field like a widget or panel.

    It has been collected from a process input/output description,
    the respective JSON schema, and from possible extension fields
    either contained in the descriptions or the JSON schemas.
    """

    model_config = ConfigDict(
        extra="allow",
    )

    name: str
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
    return _ui_field_info_from_description(name, description)


def _ui_field_info_from_output_description(
    name: str,
    description: OutputDescription,
) -> UIFieldInfo:
    return _ui_field_info_from_description(name, description)


def _ui_field_info_from_description(
    name: str, description: DescriptionType
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

    return UIFieldInfo(name=name, **ui_props)


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
