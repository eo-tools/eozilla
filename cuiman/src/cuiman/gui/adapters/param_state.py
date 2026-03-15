#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from collections.abc import Callable
from typing import Any

import param

from cuiman.api.ui import UIFieldInfo
from cuiman.api.ui.state import ValueState


class ParamValue(param.Parameterized):
    value = param.Parameter(default=None)


class ParamState(ValueState[ParamValue]):
    @classmethod
    def create(cls, field: UIFieldInfo, initial_value: Any = None) -> "ParamState":
        return ParamState(initial_value)

    def __init__(self, initial_value: Any = None):
        self.owner = ParamValue(value=initial_value)

    def get(self) -> ParamValue:
        return self.owner.value

    def set(self, value: ParamValue) -> None:
        self.owner.value = value

    def watch(
        self, observer: Callable[[ParamValue, ParamValue], None]
    ) -> Callable[[], None]:
        watcher = self.owner.param.watch(
            lambda event: observer(event.new, event.old), "value"
        )

        def unwatch() -> None:
            self.owner.param.unwatch(watcher)

        return unwatch
