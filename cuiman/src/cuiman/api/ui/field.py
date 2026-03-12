#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TypeAlias, Literal

import pydantic
from pydantic import ConfigDict

from gavicore.models import InputDescription, OutputDescription, DescriptionType

DefaultWidget: TypeAlias = Literal[
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

    widget: DefaultWidget | str | None = None
    label: str | None = None
    description: str | None = None
    tooltip: str | None = None
    placeholder: str | None = None
    group: str | None = None
    order: int | str | None = None
    advanced: bool | None = None
    password: bool | None = None
    # For slider, they default to values from JSON schema
    minimum: int | float | None = None
    maximum: int | float | None = None

    @classmethod
    def from_input_description(
        cls,
        name: str,
        description: InputDescription,
    ) -> "UIFieldInfo":
        """Extract a UI-field from the input description."""
        return _from_input_description(name, description)

    @classmethod
    def from_output_description(
        cls,
        name: str,
        description: OutputDescription,
    ) -> "UIFieldInfo":
        """Extract a UI-field from the input description."""
        return _from_output_description(name, description)


def _from_input_description(
    input_name: str, input_description: InputDescription
) -> UIFieldInfo:
    return UIFieldInfo()


def _from_output_description(
    output_name: str, output_description: OutputDescription
) -> UIFieldInfo:
    return UIFieldInfo()


def _parse_from_description(name: str, description: DescriptionType) -> UIFieldInfo:
    description_dict = description.model_dump()
    schema_dict = description_dict.get("schema") or {}
    ui_dict = any(description_dict.get("x-ui") or {}

    for field_name, field_info in description.model_fields.items():
        field_value = field_info.get("value") or field_info.get("default")

    return UIFieldInfo()
