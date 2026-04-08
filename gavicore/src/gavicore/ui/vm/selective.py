#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.ui.field.meta import FieldMeta
from gavicore.util.ensure import ensure_condition, ensure_type

from .base import ViewModel, ViewModelChangeEvent


class SelectiveViewModel(ViewModel[Any]):
    """
    A view model for values that are selected
    from a list of possible options.
    """

    def __init__(
        self,
        meta: FieldMeta,
        options: list[ViewModel],
        active_index: int = 0,
    ):
        ensure_type("meta", meta, FieldMeta)
        ensure_type("options", options, list)
        ensure_type("active_index", active_index, int)
        ensure_condition(
            0 <= active_index < len(options),
            "active_index is out of bounds",
        )
        super().__init__(meta)
        self._options = list(options)
        self._active_index = active_index
        self._unwatch_options = [
            option.watch(self._on_option_change) for option in options
        ]

    @property
    def active_index(self) -> int:
        return self._active_index

    @active_index.setter
    def active_index(self, active_index: int) -> None:
        ensure_condition(
            0 <= active_index < len(self._options), "active_index out of bounds"
        )
        self._active_index = active_index
        self._notify()

    def dispose(self):
        for unwatch_option in self._unwatch_options:
            unwatch_option()
        self._unwatch_options = []
        super().dispose()

    def _on_option_change(self, event: ViewModelChangeEvent) -> None:
        self._notify(*event.causes)

    def _get_value(self) -> Any:
        assert 0 <= self._active_index < len(self._options)
        return self._options[self._active_index].value

    def _set_value(self, value: Any) -> None:
        # Note, we expect that given value fits the option selected
        # by active index. This means this class does not and cannot
        # automatically set the right active index based on the value.
        self._options[self._active_index].value = value
