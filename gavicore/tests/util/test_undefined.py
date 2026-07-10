#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


from gavicore.util.undefined import Undefined


def test_is_defined():
    assert not Undefined.is_defined(Undefined.value)
    assert not Undefined.is_defined(Undefined())
    assert Undefined.is_defined(None)
    assert Undefined.is_defined(0)
    assert Undefined.is_defined("")
    assert Undefined.is_defined({})


def test_is_undefined():
    assert Undefined.is_undefined(Undefined.value)
    assert Undefined.is_undefined(Undefined())
    assert not Undefined.is_undefined(None)
    assert not Undefined.is_undefined(0)
    assert not Undefined.is_undefined("")
    assert not Undefined.is_undefined({})


def test_repr():
    assert repr(Undefined()) == "UNDEFINED"
    assert str(Undefined.value) == "UNDEFINED"
