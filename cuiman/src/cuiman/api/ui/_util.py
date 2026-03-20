#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


class UndefinedType:
    """Represents an undefined value."""

    __slots__ = ()

    def __repr__(self):
        return "UNDEFINED"


UNDEFINED = UndefinedType()
