#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, TypeVar

from ..fieldmeta import UIFieldMeta
from .base import ViewModel

T = TypeVar("T")


class PrimitiveViewModel(ViewModel[T]):
    """A view model that represents a primitive value."""

    def __init__(self, field_meta: UIFieldMeta, value: Any):
        super().__init__(field_meta)
        self._value = value

    def get(self) -> T:
        return self._value

    def set(self, value: T) -> None:
        if value != self._value:
            self._value = value
            self._notify_observers()
