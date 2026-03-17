#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC
from typing import Any, Callable, Generic, TypeAlias, TypeVar
from weakref import WeakSet

from .field import UIFieldInfo

T = TypeVar("T")


class _Undefined:
    """Represents an undefined value."""


_UNDEFINED = _Undefined()


FieldValueFactory: TypeAlias = Callable[[T], Any]


class FieldNodeChangeEvent:
    def __init__(self, source: "FieldNode"):
        self.source = source


FieldNodeObserver: TypeAlias = Callable[[FieldNodeChangeEvent], None]


class FieldNode(Generic[T], ABC):
    def __init__(
        self,
        field: UIFieldInfo,
        parent: "FieldNode | None" = None,
        initial_value: T | _Undefined = _UNDEFINED,
    ):
        self.field = field
        self.parent = parent
        self._value = initial_value
        self._observers: WeakSet[FieldNodeObserver] = WeakSet()

    def get(self) -> T:
        """Get the current value."""
        if isinstance(self._value, _Undefined):
            raise ValueError("Value is undefined")
        return self._value

    def set(self, value: T) -> None:
        """Set the current value."""
        self._value = value
        self._notify()

    def watch(self, *observers: FieldNodeObserver) -> Callable[[], None]:
        def unwatch():
            for o_ in observers:
                self._observers.remove(o_)

        for o in observers:
            if o not in self._observers:
                self._observers.add(o)
        return unwatch

    def _notify(self) -> None:
        event = FieldNodeChangeEvent(self)
        for observer in self._observers:
            observer(event)


class PrimitiveNode(FieldNode[T]):
    def __init__(
        self,
        field: UIFieldInfo,
        parent: "FieldNode | None" = None,
        initial_value: T | _Undefined = _UNDEFINED,
    ):
        super().__init__(field, parent=parent, initial_value=initial_value)


class ObjectNode(FieldNode[dict[str, FieldNode]]):
    def __init__(
        self,
        field: UIFieldInfo,
        parent: FieldNode | None = None,
        initial_value: dict[str, FieldNode] | _Undefined = _UNDEFINED,
    ):
        super().__init__(field, parent=parent, initial_value=initial_value)
        if not isinstance(self._value, _Undefined):
            self._watch_properties(self._value)

    def set(self, value: dict[str, FieldNode]) -> None:
        super().set(value)
        self._watch_properties(value)

    def _watch_properties(self, value: dict[str, FieldNode]):
        def property_observer(_event: FieldNodeChangeEvent):
            self._notify()

        for n in value.values():
            n.watch(property_observer)


class ArrayNode(FieldNode[list[FieldNode[T]]]):
    def __init__(
        self,
        field: UIFieldInfo,
        parent: FieldNode | None = None,
        initial_value: list[FieldNode[T]] | _Undefined = _UNDEFINED,
    ):
        super().__init__(field, parent=parent, initial_value=initial_value)
        if not isinstance(self._value, _Undefined):
            self._watch_items(self._value)

    def set(self, value: list[FieldNode[T]]) -> None:
        super().set(value)
        self._watch_items(value)

    def _watch_items(self, value: list[FieldNode[T]]):
        def item_observer(_event: FieldNodeChangeEvent):
            self._notify()

        for n in value:
            n.watch(item_observer)
