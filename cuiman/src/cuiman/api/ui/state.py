from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


Watcher = Callable[[Any], None]


class ValueState(ABC):
    @abstractmethod
    def get(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def set(self, value: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def watch(self, callback: Watcher) -> Callable[[], None]:
        raise NotImplementedError


class PlainState(ValueState):
    def __init__(self, value: Any = None):
        self._value = value
        self._watchers: list[Watcher] = []

    def get(self) -> Any:
        return self._value

    def set(self, value: Any) -> None:
        self._value = value
        for watcher in list(self._watchers):
            watcher(value)

    def watch(self, callback: Watcher) -> Callable[[], None]:
        self._watchers.append(callback)

        def unwatch() -> None:
            if callback in self._watchers:
                self._watchers.remove(callback)

        return unwatch


class StateFactory(ABC):
    @abstractmethod
    def create(self, initial: Any = None, field: Any = None) -> ValueState:
        raise NotImplementedError


class PlainStateFactory(StateFactory):
    def create(self, initial: Any = None, field: Any = None) -> ValueState:
        return PlainState(initial)
