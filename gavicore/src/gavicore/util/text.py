#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Final, Generic, TypeVar

T = TypeVar("T")

DEFAULT_SEP: Final = ","


class TextConverter(Generic[T], ABC):
    """
    Encode a (JSON) value as plain text and
    decode a (JSON) value from plain text.
    """

    Boolean: type["BooleanTextConverter"]
    Integer: type["IntegerTextConverter"]
    Number: type["NumberTextConverter"]
    String: type["StringTextConverter"]

    BooleanArray: type["BooleanArrayTextConverter"]
    IntegerArray: type["IntegerArrayTextConverter"]
    NumberArray: type["NumberArrayTextConverter"]
    StringArray: type["StringArrayTextConverter"]

    @abstractmethod
    def parse(self, text: str, **kwargs) -> T:
        """Parse text into (JSON) value of type `T`."""

    def format(self, value: T, **kwargs) -> str:
        """Format a (JSON) value of type `T` into text."""
        return str(value)


class BooleanTextConverter(TextConverter[bool]):
    def parse(self, text: str, **kwargs) -> bool:
        v = text.strip().lower()
        if v in {"true", "1"}:
            return True
        if v in {"false", "0"}:
            return False
        raise ValueError("value cannot be converted to boolean")

    def format(self, value: bool, **kwargs) -> str:
        return str(bool(value)).lower()


class IntegerTextConverter(TextConverter[int]):
    def parse(self, text: str, **kwargs) -> int:
        return int((text or "0").strip())


class NumberTextConverter(TextConverter[float]):
    def parse(self, text: str, **kwargs) -> float:
        return float((text or "0").strip())


class StringTextConverter(TextConverter[str]):
    def parse(self, text: str, **kwargs) -> str:
        return str(text)


class ArrayTextConverter(Generic[T], TextConverter[list[T]], ABC):
    def __init__(self, item_converter: TextConverter[T]):
        self._item_converter = item_converter

    def parse(self, text: str, **kwargs) -> list[T]:
        """Parse plain text into an array value with item type `T`."""
        return self.parse_array(text, **kwargs)

    def format(self, value: list[T], **kwargs) -> str:
        """Format an array value with item type `T` into plain text."""
        return self.format_array(value, **kwargs)

    def parse_array(self, text: str, sep: str | None = DEFAULT_SEP) -> list[T]:
        sep_ = None if sep is None or not sep.strip() else sep
        parts = [p.strip() for p in text.split(sep_)]
        value: list = []
        for i, p in enumerate(parts):
            try:
                v = self._item_converter.parse(p)
            except Exception as e:
                raise ValueError(f"invalid array item at index {i}") from e
            value.append(v)
        return value

    def format_array(self, value: list[T], sep: str | None = DEFAULT_SEP) -> str:
        sep_ = " " if sep is None else (f"{sep} " if sep.strip() else sep)
        return sep_.join(self._item_converter.format(v) for v in value)


class BooleanArrayTextConverter(ArrayTextConverter[bool]):
    def __init__(self):
        super().__init__(BooleanTextConverter())


class IntegerArrayTextConverter(ArrayTextConverter[int]):
    def __init__(self):
        super().__init__(IntegerTextConverter())


class NumberArrayTextConverter(ArrayTextConverter[float]):
    def __init__(self):
        super().__init__(NumberTextConverter())


class StringArrayTextConverter(ArrayTextConverter[str]):
    def __init__(self):
        super().__init__(StringTextConverter())


TextConverter.Boolean = BooleanTextConverter
TextConverter.Integer = IntegerTextConverter
TextConverter.Number = NumberTextConverter
TextConverter.String = StringTextConverter

TextConverter.BooleanArray = BooleanArrayTextConverter
TextConverter.IntegerArray = IntegerArrayTextConverter
TextConverter.NumberArray = NumberArrayTextConverter
TextConverter.StringArray = StringArrayTextConverter
