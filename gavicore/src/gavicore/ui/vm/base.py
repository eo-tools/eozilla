#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Callable, Generic, Protocol, TypeVar, TYPE_CHECKING

from gavicore.models import DataType, Schema
from gavicore.util.ensure import ensure_type
from gavicore.util.undefined import UNDEFINED, Undefined

if TYPE_CHECKING:
    from gavicore.ui.field import FieldMeta


class ViewModelChangeEvent:
    """An event emitted when a [ViewModel][ViewModel] changes."""

    def __init__(self, source: "ViewModel", *causes: "ViewModelChangeEvent"):
        self.source = source
        self.causes = causes


class ViewModelObserver(Protocol):
    """
    Type of on observer callable passed
    to the [watch][ViewModel.watch] method.
    """

    def __call__(self, event: ViewModelChangeEvent) -> None: ...


T = TypeVar("T")


class ViewModel(Generic[T], ABC):
    """Abstract base class for all view models."""

    def __init__(self, meta: "FieldMeta"):
        """Base class constructor."""
        from gavicore.ui.field import FieldMeta

        ensure_type("meta", meta, FieldMeta)
        self._meta = meta
        self._observers: set[ViewModelObserver] = set()

    @classmethod
    def from_field_meta(
        cls, meta: "FieldMeta", *, value: Any | Undefined = UNDEFINED
    ) -> "ViewModel":
        """
        Create a new view model instance from the given field metadata
        and an optional initial value.
        """
        schema = meta.schema_

        if schema.nullable:
            from .nullable import NullableViewModel

            return NullableViewModel(meta, value=value)

        if schema.type == DataType.object:
            from .object import ObjectViewModel

            return ObjectViewModel(meta, value=value)

        if schema.type == DataType.array:
            from .array import ArrayViewModel

            return ArrayViewModel(meta, value=value)

        if schema.type is not None:
            from .primitive import PrimitiveViewModel

            return PrimitiveViewModel(meta, value=value)

        raise ValueError(f"missing type in schema for field {meta.name!r}")

    @property
    def meta(self) -> "FieldMeta":
        """The field's metadata."""
        return self._meta

    @property
    def schema(self) -> Schema:
        """The field's OpenAPI schema."""
        return self._meta.schema_

    @property
    def value(self) -> T:
        """Get the current value."""
        return self._get_value()

    @value.setter
    def value(self, value: T) -> None:
        """Set the current value."""
        self._set_value(value)

    @abstractmethod
    def _get_value(self) -> T:
        """Get the current value."""

    @abstractmethod
    def _set_value(self, value: T) -> None:
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
                self._observers.discard(o1)

        for o2 in observers:
            self._observers.add(o2)
        return unwatch

    def dispose(self):
        """
        Dispose this view model.
        The default implementation removes all registered observers.
        """
        self._observers.clear()

    def _notify(self, *causes: ViewModelChangeEvent) -> None:
        """
        Notify registered observers, if any.
        To be used by derived classes only.
        """
        event = ViewModelChangeEvent(self, *causes)
        for observer in list(self._observers):
            observer(event)

    @contextmanager
    def intercept_changes(self) -> Generator[list[ViewModelChangeEvent]]:
        """
        A context manager that is used to temporarily disable
        change events fired by this view model and return all
        collected events, if any, in the order they have been collected.
        """
        prev_observers = self._observers
        recorder = ViewModelChangeRecorder()
        self._observers = {recorder}
        try:
            yield recorder.change_events
        finally:
            self._observers = prev_observers


class ViewModelChangeRecorder:
    """
    An observer that records all observed changes.
    """

    def __init__(self):
        self.change_events: list[ViewModelChangeEvent] = []

    def __call__(self, event: ViewModelChangeEvent) -> None:
        self.change_events.append(event)
