#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from inspect import ismethod
from typing import Any, Callable, Generic, TypeAlias, TypeVar
from weakref import WeakMethod, WeakSet

from gavicore.models import DataType

from ..fieldmeta import UIFieldMeta


class ViewModelChangeEvent:
    """An event emitted when a [ViewModel][ViewModel] changes."""

    def __init__(self, source: "ViewModel"):
        self.source = source


ViewModelObserver: TypeAlias = Callable[[ViewModelChangeEvent], None]
"""
Type of on observer function or method passed to the [watch][ViewModel.watch] method.
"""

T = TypeVar("T")


class ViewModel(Generic[T], ABC):
    """Abstract base class for all view models."""

    @classmethod
    def create(cls, field_meta: UIFieldMeta, value: Any) -> "ViewModel":
        """Create a new view model instance for the given field metadata
        and initial value.
        """
        schema = field_meta.schema_

        if schema.type == DataType.object:
            from .object import ObjectViewModel

            return ObjectViewModel(field_meta, value)

        if schema.type == DataType.array:
            from .array import ArrayViewModel

            return ArrayViewModel(field_meta, value)

        if schema.type is not None:
            from .primitive import PrimitiveViewModel

            return PrimitiveViewModel(field_meta, value)

        raise ValueError(f"Missing type in schema for {field_meta.name!r}")

    def __init__(self, field_meta: UIFieldMeta):
        """Constructor. Never call directly, use [create][create] instead."""
        self._field_meta = field_meta
        self._observers: WeakSet[Callable] = WeakSet()

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

    def dispose(self):
        """Dispose this view model.
        The default implementation removes all registered observers.
        """
        self._observers.clear()

    def _notify_observers(self) -> None:
        # Notify own observers, if any
        event = ViewModelChangeEvent(self)
        for observer in self._observers:
            observer(event)
