#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


from gavicore.util.undefined import UNDEFINED, UndefinedType


def test_is_defined():
    assert not UndefinedType.is_defined(UNDEFINED)
    assert not UndefinedType.is_defined(UndefinedType())
    assert UndefinedType.is_defined(None)
    assert UndefinedType.is_defined(0)
    assert UndefinedType.is_defined("")
    assert UndefinedType.is_defined({})
    assert repr(UNDEFINED) == "UNDEFINED"
    assert str(UNDEFINED) == "UNDEFINED"
