#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from inspect import ismethod
from typing import Any, Callable, Generic, TypeAlias, TypeVar
from weakref import WeakMethod, WeakSet

from gavicore.models import DataType, Schema

from ..fieldmeta import UIFieldMeta


class ViewModelChangeEvent:
    """An event emitted when a [ViewModel][ViewModel] changes."""

    def __init__(self, source: "ViewModel"):
        self.source = source


_ViewModelObserverBase: TypeAlias = Callable[[ViewModelChangeEvent], None]

ViewModelObserver: TypeAlias = (
    _ViewModelObserverBase | WeakMethod[_ViewModelObserverBase]
)
"""
Type of on observer function or method passed to the [watch][ViewModel.watch] method.
"""

T = TypeVar("T")


class ViewModel(Generic[T], ABC):
    """Abstract base class for all view models."""

    @classmethod
    def create(
        cls, field_meta: UIFieldMeta, parent: "ViewModel | None", value: Any
    ) -> "ViewModel":
        """Create a new view model instance for the given field metadata
        and initial value.
        """
        schema = field_meta.schema_

        if schema.type == DataType.object:
            from .object import ObjectViewModel

            return ObjectViewModel(field_meta, parent, value)

        if schema.type == DataType.array:
            from .array import ArrayViewModel

            return ArrayViewModel(field_meta, parent, value)

        if schema.type is not None:
            from .primitive import PrimitiveViewModel

            return PrimitiveViewModel(field_meta, parent, value)

        raise ValueError(f"Missing type in schema for {field_meta.name!r}")

    def __init__(
        self,
        field_meta: UIFieldMeta,
        parent: "ViewModel | None",
    ):
        """Constructor. Never call directly, use [create][create] instead."""
        self._field_meta = field_meta
        self._parent = parent
        self._observers: WeakSet[ViewModelObserver] = WeakSet()

    @property
    def field_meta(self) -> UIFieldMeta:
        return self._field_meta

    @property
    def nullable(self) -> bool:
        return self._field_meta.schema_.nullable is True

    @abstractmethod
    def get(self) -> T:
        """Get the current value."""

    @abstractmethod
    def set(self, value: T) -> None:
        """Set the current value."""

    def watch(self, *observers: ViewModelObserver) -> Callable[[], None]:
        def unwatch():
            for o1 in observers:
                self._observers.remove(o1)

        for o2 in observers:
            o3 = WeakMethod(o2) if ismethod(o2) else o2
            if o3 not in self._observers:
                self._observers.add(o3)
        return unwatch

    def _notify_observers(self) -> None:
        # Notify own observers, if any
        event = ViewModelChangeEvent(self)
        for observer in self._observers:
            observer(event)
        # Also notify parent, if any
        if self._parent is not None:
            self._parent._notify_observers()


def get_initial_value(field_meta: UIFieldMeta) -> Any:
    schema = field_meta.schema_
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
            assert len(field_meta.children) == 1
            item_meta = field_meta.children[0]
            return [get_initial_value(item_meta) for _i in range(min_items)]
        case DataType.object:
            # TODO: consider minProperties, additionalProperties
            required = set(schema.required or [])
            return {
                item_meta.name: get_initial_value(item_meta)
                for item_meta in field_meta.children
                if item_meta.name in required
            }
        case _:
            raise ValueError(
                f"Unsupported schema {schema.type} in field {field_meta.name!r}"
            )


def get_initial_number(schema: Schema) -> int | float:
    v = 0
    if schema.minimum is not None:
        v = min(v, schema.minimum)
    if schema.maximum is not None:
        v = min(v, schema.maximum)
    return v
