#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
from abc import ABC, abstractmethod
from types import NoneType
from typing import Any, Final, Literal, TypeAlias

from gavicore.util.ensure import ensure_type

JSON_TYPE_NAMES: Final = ("boolean", "integer", "number", "string", "array", "object")

JsonType: TypeAlias = Literal[
    "boolean", "integer", "number", "string", "array", "object"
]
JsonValue: TypeAlias = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)
JsonSchemaDict: TypeAlias = dict[str, JsonValue]

JSON_PYTHON_TYPES = (bool, int, float, str, list, dict, NoneType)


class JsonCodec(ABC):
    """Convert component values to/from JSON values."""

    @abstractmethod
    def to_json(self, value: Any) -> JsonValue:
        """Return a JSON value from given Python value."""

    @abstractmethod
    def from_json(self, json_value: JsonValue) -> Any:
        """Return a Python value from given JSON value."""


class JsonIdentityCodec(JsonCodec):
    def to_json(self, value: Any) -> JsonValue:
        ensure_type("value", value, JSON_PYTHON_TYPES)
        return value

    def from_json(self, json_value: JsonValue) -> Any:
        ensure_type("json_value", json_value, JSON_PYTHON_TYPES)
        return json_value


class JsonDateCodec(JsonCodec):
    def to_json(self, value: Any) -> JsonValue:
        if not value:
            return None
        ensure_type("value", value, datetime.date)
        assert isinstance(value, datetime.date)
        return datetime.date.isoformat(value)

    def from_json(self, json_value: JsonValue) -> Any:
        if not json_value:
            return None
        ensure_type("json_value", json_value, str)
        assert isinstance(json_value, str)
        return datetime.date.fromisoformat(json_value)
