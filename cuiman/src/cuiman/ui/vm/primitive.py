#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Generic, TypeVar

from .._util import UNDEFINED, UndefinedType
from ..fieldmeta import UIFieldMeta
from .base import ViewModel

T = TypeVar("T", bool, int, float, str)


class PrimitiveViewModel(Generic[T], ViewModel[T]):
    """
    A view model that represents a non-nullable, primitive value.
    """

    def __init__(
        self, field_meta: UIFieldMeta, *, value: Any | UndefinedType = UNDEFINED
    ):
        super().__init__(field_meta)
        if field_meta.nullable:
            raise ValueError("field_meta must not be nullable")
        self._value: T
        if UndefinedType.is_defined(value):
            if value is None:
                raise ValueError("value must not be None")
            self._value = value  # type: ignore[assignment]
        else:
            self._value = UIFieldMeta.get_initial_value(field_meta)

    def _get_value(self) -> T:
        return self._value

    def _set_value(self, value: T) -> None:
        if value != self._value:
            self._value = value
            self._notify()
