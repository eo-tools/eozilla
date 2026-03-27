#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


# noinspection PyMethodMayBeStatic
class ArrayTextConverter(Generic[T], ABC):
    Boolean: type["_BooleanArrayTextConverter"]
    Integer: type["_IntegerArrayTextConverter"]
    Number: type["_NumberArrayTextConverter"]
    String: type["_StringArrayTextConverter"]

    @abstractmethod
    def parse_item(self, text: str) -> T:
        """Parse a value from text."""

    def format_item(self, value: T) -> str:
        """Format a value into text."""
        return str(value)

    def parse_array(self, text: str, sep: str | None = ",") -> list[T]:
        sep_ = None if sep is None or not sep.strip() else sep
        parts = [p.strip() for p in text.split(sep_)]
        value: list = []
        for i, p in enumerate(parts):
            try:
                v = self.parse_item(p)
            except Exception as e:
                raise ValueError(f"invalid array item at index {i}") from e
            value.append(v)
        return value

    def format_array(self, value: list[T], sep: str | None = ",") -> str:
        sep_ = " " if sep is None else (f"{sep} " if sep.strip() else sep)
        return sep_.join(self.format_item(v) for v in value)


class _BooleanArrayTextConverter(ArrayTextConverter[bool]):
    def parse_item(self, text: str) -> bool:
        v = text.strip().lower()
        if v in {"true", "1"}:
            return True
        if v in {"false", "0"}:
            return False
        raise ValueError("value cannot be converted to boolean")

    def format_item(self, value: bool) -> str:
        return super().format_item(value).lower()


class _IntegerArrayTextConverter(ArrayTextConverter[int]):
    def parse_item(self, text: str) -> int:
        return int(text.strip())


class _NumberArrayTextConverter(ArrayTextConverter[float]):
    def parse_item(self, text: str) -> float:
        return float(text.strip())


class _StringArrayTextConverter(ArrayTextConverter[str]):
    def parse_item(self, text: str) -> str:
        return text.strip()


ArrayTextConverter.Boolean = _BooleanArrayTextConverter
ArrayTextConverter.Integer = _IntegerArrayTextConverter
ArrayTextConverter.Number = _NumberArrayTextConverter
ArrayTextConverter.String = _StringArrayTextConverter
