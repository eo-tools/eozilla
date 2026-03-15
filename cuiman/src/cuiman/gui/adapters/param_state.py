from __future__ import annotations

from collections.abc import Callable
from typing import Any

import param

from cuiman.api.ui import UIFieldInfo
from cuiman.api.ui.state import ValueState


class _ParamValue(param.Parameterized):
    value = param.Parameter(default=None)


class ParamState(ValueState):
    @classmethod
    def create(cls, field: UIFieldInfo, initial_value: Any = None) -> ParamState:
        return ParamState(initial_value)

    def __init__(self, initial: Any = None):
        self.owner = _ParamValue(value=initial)

    def get(self) -> Any:
        return self.owner.value

    def set(self, value: Any) -> None:
        self.owner.value = value

    def watch(self, observer: Callable[[Any], None]) -> Callable[[], None]:
        watcher = self.owner.param.watch(lambda event: observer(event.new), "value")

        def unwatch() -> None:
            self.owner.param.unwatch(watcher)

        return unwatch
