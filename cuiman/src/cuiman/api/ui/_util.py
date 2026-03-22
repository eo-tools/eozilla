#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Any


class UndefinedType:
    """Represents an undefined value."""

    __slots__ = ()

    @staticmethod
    def is_defined(value: Any) -> bool:
        return not isinstance(value, UndefinedType)

    def __repr__(self):
        return "UNDEFINED"


UNDEFINED = UndefinedType()
