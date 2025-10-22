#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pytest

# noinspection PyProtectedMember
from s2gos_common.util.obj import _nest_one, flatten_obj, nest_dict, nest_obj


def test_flatten_and_nest_dict_1():
    nested = {"a": {"b": {"c": 1}}}
    flat = flatten_obj(nested)
    assert flat == {"a.b.c": 1}
    assert nest_dict(flat) == nested


def test_flatten_and_nest_dict_2():
    nested = {"a": {"b": {}, "d": {}}, "f": 0}
    flat = flatten_obj(nested)
    assert flat == {"a.b": {}, "a.d": {}, "f": 0}
    assert nest_dict(flat) == nested


def test_flatten_and_nest_dict_only():
    nested = {"a": {"b": {"c": 1}}}
    flat = flatten_obj(nested)
    assert flat == {"a.b.c": 1}
    assert nest_obj(flat) == nested


def test_flatten_and_nest_list_only():
    nested = [1, 2, [3, 4]]
    flat = flatten_obj(nested, flatten_lists=True)
    assert flat == {"0": 1, "1": 2, "2.0": 3, "2.1": 4}
    assert nest_obj(flat) == nested


def test_flatten_and_nest_mixed():
    nested = {"a": [{"x": 1}, {"y": 2}], "b": 3}
    flat = flatten_obj(nested, flatten_lists=True)
    assert flat == {"a.0.x": 1, "a.1.y": 2, "b": 3}
    assert nest_obj(flat) == nested


def test_overwrite_and_sparse_lists():
    flat = {"a.0": "first", "a.2": "third"}
    nested = nest_obj(flat)
    assert nested == {"a": ["first", None, "third"]}
    assert flatten_obj(nested, flatten_lists=True) == flat


def test_nest_fail():
    with pytest.raises(TypeError, match="expected key of type str, got int"):
        nest_obj({"a.b": 13, "a.0": 14})

    with pytest.raises(TypeError, match="expected index of type int, got str"):
        nest_obj({"a.0": 13, "a.b": 14})

    with pytest.raises(TypeError, match="expected a list or a dict, got int"):
        # noinspection PyTypeChecker
        nest_obj({"a.b": 13, "a.c": 14}, root=0)


def test_nest_one_into_dict():
    nested = _nest_one({}, "a", 13)
    assert nested == {"a": 13}

    nested = _nest_one({}, "a.b", 13)
    assert nested == {"a": {"b": 13}}

    nested = _nest_one({}, "a.b.c", 13)
    assert nested == {"a": {"b": {"c": 13}}}

    with pytest.raises(TypeError):
        _nest_one([], "a.b.c", 13)


def test_nest_one_into_list():
    nested = _nest_one([], "0", 13)
    assert nested == [13]

    nested = _nest_one([], "0.b", 13)
    assert nested == [{"b": 13}]

    nested = _nest_one([], "0.b.c", 13)
    assert nested == [{"b": {"c": 13}}]

    with pytest.raises(TypeError):
        _nest_one([], "a", 13)

    # nested = nest_one({}, "0.a.b", 13)
    # assert nested == [{"a": {"b": 13}}]
