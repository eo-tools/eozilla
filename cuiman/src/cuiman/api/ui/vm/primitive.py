#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Generic, TypeVar

from ..fieldmeta import UIFieldMeta
from .base import ViewModel

T = TypeVar("T", bool, int, float, str)


class PrimitiveViewModel(Generic[T], ViewModel[T]):
    """
    A view model that represents a non-nullable, primitive value.
    """

    def __init__(self, field_meta: UIFieldMeta, initial_value: Any):
        super().__init__(field_meta)
        if field_meta.nullable:
            raise ValueError("field_meta must not be nullable")
        self._value = initial_value

    def get(self) -> T:
        return self._value

    def set(self, value: T) -> None:
        if value != self._value:
            self._value = value
            self._notify_observers()
