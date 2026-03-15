from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeAlias, TypeVar

from cuiman.api.ui import UIFieldInfo

T = TypeVar("T")
Observer: TypeAlias = Callable[[T, T], None]


class ValueState(Generic[T], ABC):
    """A simple abstraction of a reactive value."""

    @classmethod
    @abstractmethod
    def create(
        cls, field: UIFieldInfo, initial_value: T | None = None
    ) -> "ValueState[T]":
        """Create an instance of this class given the initial value
        and UI field metadata.
        """

    @abstractmethod
    def get(self) -> T:
        """Get the current value."""

    @abstractmethod
    def set(self, value: T) -> None:
        """Set the new value and inform observers."""

    @abstractmethod
    def watch(self, observer: Observer[T]) -> Callable[[], None]:
        """Add an observer to the observers list.

        Args:
            observer: Observer callback to add
        Returns:
            A no-arg void function `unsubscribe()` that when called,
            removes the added observer.
        """


class DefaultValueState(ValueState):
    """Default implementation of a reactive value."""

    def __init__(self, value: Any = None):
        self._value = value
        self._observers: list[Observer] = []

    @classmethod
    def create(cls, field: UIFieldInfo = None, initial_value: Any = None) -> ValueState:
        return DefaultValueState(initial_value)

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        old_value = self._value
        self._value = value
        for observer in list(self._observers):
            observer(value, old_value)

    def watch(self, callback: Observer) -> Callable[[], None]:
        self._observers.append(callback)

        def unwatch() -> None:
            if callback in self._observers:
                self._observers.remove(callback)

        return unwatch
