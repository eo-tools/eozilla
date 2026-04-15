#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import base64
import datetime
from abc import ABC, abstractmethod
from types import NoneType
from typing import Any, Final, Generic, Literal, TypeAlias, TypeVar

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

T = TypeVar("T")


class JsonCodec(ABC, Generic[T]):
    """Convert component values to/from JSON values."""

    @abstractmethod
    def to_json(self, value: T | None) -> JsonValue:
        """Return a JSON value from given Python value."""

    @abstractmethod
    def from_json(self, json_value: JsonValue) -> T | None:
        """Return a Python value from given JSON value."""


class JsonIdentityCodec(JsonCodec[Any]):
    def to_json(self, value: Any) -> JsonValue:
        ensure_type("value", value, JSON_PYTHON_TYPES)
        return value

    def from_json(self, json_value: JsonValue) -> Any:
        ensure_type("json_value", json_value, JSON_PYTHON_TYPES)
        return json_value


class JsonBase64Codec(JsonCodec[bytes | str]):
    def to_json(self, value: bytes | str | None) -> JsonValue:
        if not value:
            return None
        ensure_type("value", value, (bytes, str))
        assert isinstance(value, (bytes, str))
        encoded_bytes = base64.b64encode(
            value if isinstance(value, bytes) else value.encode("utf-8")
        )
        return encoded_bytes.decode("utf-8")

    def from_json(self, json_value: JsonValue) -> bytes | str | None:
        if not json_value:
            return None
        ensure_type("json_value", json_value, str)
        assert isinstance(json_value, str)
        return base64.b64decode(json_value)  # always type bytes


class JsonDateTimeCodec(JsonCodec[datetime.datetime]):
    def to_json(self, value: datetime.datetime | None) -> JsonValue:
        if not value:
            return None
        ensure_type("value", value, datetime.datetime)
        assert isinstance(value, datetime.datetime)
        return datetime.datetime.isoformat(value)

    def from_json(self, json_value: JsonValue) -> datetime.datetime | None:
        if not json_value:
            return None
        ensure_type("json_value", json_value, str)
        assert isinstance(json_value, str)
        return datetime.datetime.fromisoformat(json_value)


class JsonDateCodec(JsonCodec[datetime.date]):
    def to_json(self, value: datetime.date | None) -> JsonValue:
        if not value:
            return None
        ensure_type("value", value, datetime.date)
        assert isinstance(value, datetime.date)
        return datetime.date.isoformat(value)

    def from_json(self, json_value: JsonValue) -> datetime.date | None:
        if not json_value:
            return None
        ensure_type("json_value", json_value, str)
        assert isinstance(json_value, str)
        return datetime.date.fromisoformat(json_value)


class JsonTimeCodec(JsonCodec[datetime.time]):
    def to_json(self, value: datetime.time | None) -> JsonValue:
        if not value:
            return None
        ensure_type("value", value, datetime.time)
        assert isinstance(value, datetime.time)
        return datetime.time.isoformat(value)

    def from_json(self, json_value: JsonValue) -> datetime.time | None:
        if not json_value:
            return None
        ensure_type("json_value", json_value, str)
        assert isinstance(json_value, str)
        return datetime.time.fromisoformat(json_value)
