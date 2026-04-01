#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


import pytest

from gavicore.util.ensure import ensure_type, ensure_condition, ensure_callable


def test_ensure_type():
    ensure_type("x", 12, int)
    ensure_type("x", 12, (int, str))
    ensure_type("x", "12", (int, str))
    with pytest.raises(TypeError, match="x must have type int, but was str"):
        ensure_type("x", "12", int)
    with pytest.raises(TypeError, match="x must have type str, but was int"):
        ensure_type("x", 12, str)
    with pytest.raises(TypeError, match="x must have type int or str, but was list"):
        ensure_type("x", [1, 2, 3], (int, str))


def test_ensure_callable():
    ensure_callable("cb", test_ensure_type)
    with pytest.raises(TypeError, match="cb must be callable, but was bool"):
        # noinspection PyTypeChecker
        ensure_callable("cb", False)


def test_ensure_condition():
    ensure_condition(True, lambda: "ohoh")
    with pytest.raises(ValueError, match="oh no"):
        ensure_condition(False, "oh no")
    with pytest.raises(ValueError, match="no, no"):
        ensure_condition(False, lambda: "no, no")
