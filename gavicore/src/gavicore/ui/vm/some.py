#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.util.undefined import Undefined

from ..field.meta import FieldMeta
from .base import ViewModel


class AnyViewModel(ViewModel[Any]):
    """
    A view model that can represent any value.
    """

    def __init__(
        self, meta: FieldMeta, *, value: Any | Undefined = Undefined.value
    ) -> None:
        super().__init__(meta)
        self._value = (
            value if Undefined.is_defined(value) else FieldMeta.get_initial_value(meta)
        )

    def _get_value(self) -> Any:
        return self._value

    def _set_value(self, value: Any) -> None:
        if value != self._value:
            self._value = value
            self._notify()
