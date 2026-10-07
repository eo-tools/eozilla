"""Lazy package exports retain the public Python API."""

import pytest

import cuiman
import cuiman.api


def test_public_api_exports_are_discoverable_and_cached():
    assert set(cuiman.__all__) <= set(dir(cuiman))
    for name in cuiman.__all__:
        if name == "__version__":
            continue
        value = cuiman.__getattr__(name)
        assert value is getattr(cuiman.api, name)
        assert vars(cuiman)[name] is value


def test_unknown_package_attribute_raises_attribute_error():
    with pytest.raises(AttributeError, match="has no attribute 'missing_export'"):
        getattr(cuiman, "missing_export")
