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

    def __init__(
        self, source: "ViewModel", cause: "ViewModelChangeEvent | None" = None
    ):
        self.source = source
        self.cause = cause


ViewModelObserver: TypeAlias = Callable[[ViewModelChangeEvent], None]
"""
Type of on observer function or method passed to the [watch][ViewModel.watch] method.
"""

T = TypeVar("T")


class ViewModel(Generic[T], ABC):
    """Abstract base class for all view models."""

    def __init__(self, field_meta: UIFieldMeta):
        """Base class constructor."""
        if not isinstance(field_meta, UIFieldMeta):
            raise TypeError(f"field_meta must have type {UIFieldMeta.__name__!r}")
        self._field_meta = field_meta
        self._observers: WeakSet[Callable] = WeakSet()

    @classmethod
    def create(cls, field_meta: UIFieldMeta, value: Any) -> "ViewModel":
        """
        Create a new view model instance for the given field metadata
        and initial value.
        """
        schema = field_meta.schema_

        if schema.nullable:
            from .nullable import NullableViewModel

            return NullableViewModel(field_meta, value)

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

    @property
    def field_meta(self) -> UIFieldMeta:
        """The field metadata."""
        return self._field_meta

    @abstractmethod
    def get(self) -> T:
        """Get the current value."""

    @abstractmethod
    def set(self, value: T) -> None:
        """Set the current value."""

    def watch(self, *observers: ViewModelObserver) -> Callable[[], None]:
        """
        Watch this view model by adding one or more observers to it.

        Args:
            observers: The observer(s) to add.
        Returns:
            A function `unwatch()` that, when called, removes the added observer(s).
        """

        def unwatch():
            for o1 in observers:
                self._observers.remove(o1)

        for o2 in observers:
            o3 = WeakMethod(o2) if ismethod(o2) else o2
            if o3 not in self._observers:
                self._observers.add(o3)
        return unwatch

    def dispose(self):
        """
        Dispose this view model.
        The default implementation removes all registered observers.
        """
        self._observers.clear()

    def _notify_observers(self, cause: ViewModelChangeEvent | None = None) -> None:
        """
        Notify own observers, if any.
        To be used by derived classes only.
        """
        event = ViewModelChangeEvent(self, cause=cause)
        for observer in self._observers:
            observer(event)
