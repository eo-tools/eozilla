#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any


class Undefined:
    """The type of an undefined value."""

    __slots__ = ()

    value: "Undefined"
    """The value of an undefined value."""

    @staticmethod
    def is_undefined(value: Any) -> bool:
        """Test if the given value is undefined."""
        return isinstance(value, Undefined)

    @staticmethod
    def is_defined(value: Any) -> bool:
        """Test if the given value is not undefined."""
        return not isinstance(value, Undefined)

    def __repr__(self):
        return "UNDEFINED"


UNDEFINED = Undefined()
Undefined.value = Undefined()
