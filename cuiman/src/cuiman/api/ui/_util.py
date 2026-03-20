#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any


class Undefined:
    """Represents an undefined value."""

    value: "Undefined"
    """An instance of the undefined."""

    @classmethod
    def is_undefined(cls, value: Any) -> bool:
        return isinstance(value, Undefined)

    @classmethod
    def is_defined(cls, value: Any) -> bool:
        return not isinstance(value, Undefined)


Undefined.value = Undefined()
