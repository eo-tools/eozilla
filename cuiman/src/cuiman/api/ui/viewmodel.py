#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Callable, Generic, TypeAlias, TypeVar
from weakref import WeakSet

from gavicore.models import DataType, Schema
from .uifieldinfo import UIFieldInfo

T = TypeVar("T")


class _Undefined:
    """Represents an undefined value."""


_UNDEFINED = _Undefined()


class ViewModelChangeEvent:
    def __init__(self, source: "ViewModel"):
        self.source = source


ViewModelObserver: TypeAlias = Callable[[ViewModelChangeEvent], None]


class ViewModel(Generic[T], ABC):
    def __init__(
        self,
        field_info: UIFieldInfo,
    ):
        self.field_info = field_info
        self._value = get_initial_value(field_info)
        self._observers: WeakSet[ViewModelObserver] = WeakSet()

    def get(self) -> T:
        """Get the current value."""
        if isinstance(self._value, _Undefined):
            raise ValueError("Value is undefined")
        return self._value

    def set(self, value: T) -> None:
        """Set the current value."""
        self._value = value
        self._notify()

    def watch(self, *observers: ViewModelObserver) -> Callable[[], None]:
        def unwatch():
            for o_ in observers:
                self._observers.remove(o_)

        for o in observers:
            if o not in self._observers:
                self._observers.add(o)
        return unwatch

    def _notify(self) -> None:
        event = ViewModelChangeEvent(self)
        for observer in self._observers:
            observer(event)


class PrimitiveViewModel(ViewModel[T]):
    """A view model that represents a primitive value."""


class CompositeViewModel(Generic[T], ViewModel[T], ABC):
    """A view model that represents a composite value."""

    def __init__(
        self,
        field_info: UIFieldInfo,
    ):
        super().__init__(field_info)
        if not isinstance(self._value, _Undefined):
            self._watch_items(self._value)

    def set(self, value: T) -> None:
        super().set(value)
        self._watch_items(value)

    def _watch_items(self, value: T):
        def property_observer(_event: ViewModelChangeEvent):
            self._notify()

        for n in self._items(value):
            n.watch(property_observer)

    @abstractmethod
    def _items(self, value: T) -> Sequence[ViewModel]:
        """Get child items."""
        if isinstance(self._value, dict):
            return list(self._value.values())
        else:
            return []


class ObjectViewModel(CompositeViewModel[dict[str, ViewModel]]):
    def _items(self, value: T) -> Sequence[ViewModel]:
        if isinstance(self._value, dict):
            return list(self._value.values())
        else:
            return []


class ArrayViewModel(CompositeViewModel[list[ViewModel[T]]]):
    def _items(self, value: T) -> Sequence[ViewModel]:
        if isinstance(self._value, list):
            return self._value
        else:
            return []


def get_initial_value(field_info: UIFieldInfo) -> Any:
    schema = field_info.schema_
    if schema.default is not None:
        return schema.default
    if schema.nullable:
        return None
    match schema.type:
        case DataType.boolean:
            return False
        case DataType.integer:
            return int(get_initial_number(schema))
        case DataType.number:
            return float(get_initial_number(schema))
        case DataType.string:
            min_length = schema.minLength if schema.minLength is not None else 0
            return "a" * min_length
        case DataType.array:
            min_items = schema.minItems if schema.minItems is not None else 0
            assert len(field_info.children) == 1
            item_field_info = field_info.children[0]
            return [get_initial_value(item_field_info) for _i in range(min_items)]
        case DataType.object:
            # TODO: consider minProperties, additionalProperties
            required = set(schema.required or [])
            return {
                fi.name: get_initial_value(fi)
                for fi in field_info.children
                if fi.name in required
            }
        case _:
            return _UNDEFINED


def get_initial_number(schema: Schema) -> int | float:
    v = 0
    if schema.minimum is not None:
        v = min(v, schema.minimum)
    if schema.maximum is not None:
        v = min(v, schema.maximum)
    return v
