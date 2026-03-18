#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Callable, Generic, TypeAlias, TypeVar
from weakref import WeakMethod, WeakSet
from inspect import ismethod

from gavicore.models import DataType, Schema
from .uifieldinfo import UIFieldInfo

T = TypeVar("T")


class _Undefined:
    """Represents an undefined value."""


_UNDEFINED = _Undefined()


def is_undefined(value: T) -> bool:
    return isinstance(value, _Undefined)


class ViewModelChangeEvent:
    def __init__(self, source: "ViewModel"):
        self.source = source


ViewModelObserverBase: TypeAlias = Callable[[ViewModelChangeEvent], None]
ViewModelObserver: TypeAlias = ViewModelObserverBase | WeakMethod[ViewModelObserverBase]


class ViewModel(Generic[T], ABC):
    @classmethod
    def create(
        cls, field_info: UIFieldInfo, parent: "ViewModel | None", initial_value: Any
    ) -> "ViewModel":
        schema = field_info.schema_
        if schema.type == DataType.object:
            return ObjectViewModel(field_info, parent, initial_value)
        if schema.type == DataType.array:
            return ArrayViewModel(field_info, parent, initial_value)
        if schema.type is not None:
            return PrimitiveViewModel(field_info, parent, initial_value)
        raise ValueError(f"Missing type in schema for {field_info.name!r}")

    def __init__(
        self,
        field_info: UIFieldInfo,
        parent: "ViewModel | None",
    ):
        self._field_info = field_info
        self._parent = parent
        self._observers: WeakSet[ViewModelObserver] = WeakSet()

    @property
    @abstractmethod
    def defined(self) -> bool:
        """Is this model defined."""

    @abstractmethod
    def get(self) -> T:
        """Get the current value."""

    @abstractmethod
    def set(self, value: T) -> None:
        """Set the current value."""

    def watch(self, *observers: ViewModelObserver) -> Callable[[], None]:
        def unwatch():
            for o_ in observers:
                self._observers.remove(o_)

        for o in observers:
            if o not in self._observers:
                if ismethod(o):
                    self._observers.add(WeakMethod(o))
                else:
                    self._observers.add(o)
        return unwatch

    def _notify_observers(self) -> None:
        event = ViewModelChangeEvent(self)
        for observer in self._observers:
            observer(event)


class PrimitiveViewModel(ViewModel[T]):
    """A view model that represents a primitive value."""

    def __init__(
        self, field_info: UIFieldInfo, parent: "ViewModel | None", initial_value: Any
    ):
        super().__init__(field_info, parent)
        self.field_info = field_info
        self.parent = parent
        if is_undefined(initial_value):
            self._value = get_initial_value(field_info)
        else:
            self._value = initial_value

    @property
    def defined(self) -> bool:
        """Is this model defined."""
        return not is_undefined(self._value)

    def get(self) -> T:
        """Get the current value."""
        self._assert_defined()
        return self._value

    def set(self, value: T) -> None:
        """Set the current value."""
        self._assert_defined()
        if value != self._value:
            self._value = value
            self._notify_observers()

    def _assert_defined(self) -> None:
        if not self.defined:
            raise ValueError(f"Value for {self._field_info.name!r} is undefined")


class CompositeViewModel(Generic[T], ViewModel[T], ABC):
    """A view model that represents a composite value."""

    def __init__(
        self,
        field_info: UIFieldInfo,
        initial_value: Any,
    ):
        super().__init__(field_info, initial_value)
        if not isinstance(self._value, _Undefined):
            self._watch_items(self._value)

    def set(self, value: T) -> None:
        super().set(value)
        self._watch_items(value)

    def _watch_items(self, value: T):
        def property_observer(_event: ViewModelChangeEvent):
            self._notify_observers()

        for n in self._items(value):
            n.watch(property_observer)

    @abstractmethod
    def _items(self, value: T) -> Sequence[ViewModel]:
        """Get child items."""
        if isinstance(self._value, dict):
            return list(self._value.values())
        else:
            return []


class ObjectViewModel(ViewModel[dict[str, Any]]):
    def __init__(
        self, field_info: UIFieldInfo, parent: ViewModel | None, initial_value: Any
    ):
        super().__init__(field_info, parent)
        if isinstance(initial_value, dict):
            value = initial_value
        elif is_undefined(initial_value):
            value = {}
        else:
            raise ValueError(
                f"Type of initial value must be dict for {field_info.name!r}"
            )

        self._vm_children = {
            fi.name: self.create(field_info, self, value.get(fi.name, _UNDEFINED))
            for fi in field_info.children
        }
        self._cached_value = value

    def get(self) -> dict[str, Any]:
        return {k: v for k, v in self._vm_children.items()}

    def set(self, value: dict[str, Any]) -> None:
        if not is_undefined(value):
            raise TypeError(
                f"Type of value must be dict for field {self._field_info.name!r}"
            )
        for k, v in value.items():
            vm = self._vm_children[k]
            vm.set(v)

    def __len__(self) -> int:
        self.assert_defined_value(self._value)
        return len(self._vm_children)

    def __getitem__(self, key: str) -> Any:
        self.assert_defined_value(self._value)
        vm = self._vm_children[key]
        return vm.get()

    def __setitem__(self, key: str, value: Any) -> None:
        self.assert_defined_value(value)
        self.assert_defined_value(self._value)
        vm = self._vm_children[key]
        vm.set(value)


class ArrayViewModel(ViewModel[list[T]]):
    def __init__(self, field_info: UIFieldInfo, initial_value: Any):
        super().__init__(field_info, initial_value)
        if isinstance(self._value, list):
            self._vm_children = [
                self.create(field_info.children[0], v) for v in self._value
            ]
        elif not is_undefined(self._value):
            raise ValueError(
                f"Type of initial value must be list for {field_info.name!r}"
            )


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
