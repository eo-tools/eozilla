#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.resolver import (
    JobResultResolverRegistry,
    ResolutionContext,
    resolve_job_result,
)
from cuiman.api.resolver.impl import StacResolver, ValueResolver


def test_initially_empty_and_default():
    assert JobResultResolverRegistry().resolver_types == ()
    assert JobResultResolverRegistry.create_default().resolver_types == (
        StacResolver,
        ValueResolver,
    )


def test_registration_order_duplicates_and_tuple_snapshots():
    registry = JobResultResolverRegistry()
    registry.register(_First)
    snapshot = registry.resolver_types
    registry.register(_Second)
    registry.register(_Third)
    assert registry.resolver_types == (_Third, _Second, _First)
    registry.register(_First)
    assert registry.resolver_types == (_First, _Third, _Second)
    assert snapshot == (_First,)


def test_unregister_and_clear_are_isolated_and_idempotent():
    registry = JobResultResolverRegistry()
    other = JobResultResolverRegistry()
    unregister_first = registry.register(_First)
    unregister_second = registry.register(_Second)
    other.register(_First)
    unregister_first()
    unregister_first()
    assert registry.resolver_types == (_Second,)
    assert other.resolver_types == (_First,)
    registry.clear()
    registry.clear()
    unregister_second()
    assert registry.resolver_types == ()
    registry.register(_Third)
    assert registry.resolver_types == (_Third,)


@pytest.mark.parametrize("invalid", [int, object, ValueResolver(), None])
def test_invalid_registration_preserves_registry(invalid):
    registry = JobResultResolverRegistry.create_default()
    with pytest.raises(TypeError, match="JobResultResolver subclass"):
        registry.register(invalid)
    assert registry.resolver_types == (StacResolver, ValueResolver)


def test_configuration_registry_caching_and_isolation():
    class Application(ClientConfig):
        extra_job_result_resolvers = (_First,)

    class Child(Application):
        pass

    class Other(ClientConfig):
        pass

    registry = Application.get_job_result_resolver_registry()
    assert Application.get_job_result_resolver_registry() is registry
    child = Child.get_job_result_resolver_registry()
    assert child is not registry
    assert child.resolver_types == (_First, StacResolver, ValueResolver)
    assert (
        Other.get_job_result_resolver_registry()
        is not ClientConfig.get_job_result_resolver_registry()
    )
    registry.clear()
    assert Application.get_job_result_resolver_registry().resolver_types == ()
    assert child.resolver_types == (_First, StacResolver, ValueResolver)
    assert Other.get_job_result_resolver_registry().resolver_types == (
        StacResolver,
        ValueResolver,
    )
    unregister = Application.register_job_result_resolver(_Second)
    assert registry.resolver_types == (_Second,)
    unregister()
    assert registry.resolver_types == ()


@pytest.mark.asyncio
async def test_default_registry_dispatches_stac_before_value():
    registry = JobResultResolverRegistry.create_default()
    item = {
        "type": "Feature",
        "stac_version": "1.1.0",
        "id": "item",
        "geometry": None,
        "properties": {},
        "links": [],
        "assets": {},
    }
    listing = await resolve_job_result(
        ResolutionContext("x", item), *registry.resolver_types
    )
    assert listing[0].kind == "stac-item"
    listing = await resolve_job_result(
        ResolutionContext("x", {"ordinary": True}), *registry.resolver_types
    )
    assert listing[0].kind == "value"
    assert listing[0].value == {"ordinary": True}


class _First(ValueResolver):
    pass


class _Second(_First):
    pass


class _Third(_First):
    pass
