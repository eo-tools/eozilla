from __future__ import annotations

from collections.abc import Callable
from typing import Any

import param

from cuiman.api.ui.state import StateFactory, ValueState


class _ParamValue(param.Parameterized):
    value = param.Parameter(default=None)


class ParamState(ValueState):
    def __init__(self, initial: Any = None):
        self.owner = _ParamValue(value=initial)

    def get(self) -> Any:
        return self.owner.value

    def set(self, value: Any) -> None:
        self.owner.value = value

    def watch(self, callback: Callable[[Any], None]) -> Callable[[], None]:
        watcher = self.owner.param.watch(lambda event: callback(event.new), "value")

        def unwatch() -> None:
            self.owner.param.unwatch(watcher)

        return unwatch


class ParamStateFactory(StateFactory):
    def create(self, initial: Any = None, field: Any = None) -> ParamState:
        return ParamState(initial)
