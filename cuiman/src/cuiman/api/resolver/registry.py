#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Ordered discovery extensions, independent of discovery operation state."""

from typing import Callable

from .resolver import JobResultResolver, assert_resolver_type_valid


class JobResultResolverRegistry:
    """A registry of resolver classes, with later registrations taking priority.

    This selects the interpretations dispatch considers, letting application
    resolvers precede built-in STAC recognition and the generic value fallback.
    Registries contain classes, not instances, loaders, or transformation state.
    Client configuration maintains an independent registry per concrete class.
    """

    def __init__(self):
        self._resolver_types: list[type[JobResultResolver]] = []

    @classmethod
    def create_default(cls) -> "JobResultResolverRegistry":
        """Create a registry with STAC discovery before the generic value resolver."""
        from .impl import StacResolver, ValueResolver

        registry = cls()
        registry.register(ValueResolver)
        registry.register(StacResolver)
        return registry

    @property
    def resolver_types(self) -> tuple[type[JobResultResolver], ...]:
        """Registered resolver classes in dispatch order, as a tuple snapshot."""
        return tuple(self._resolver_types)

    def register(self, resolver_type: type[JobResultResolver]) -> Callable[[], None]:
        """Validate and register a resolver with highest priority.

        Registering an existing class moves it to the front without duplicating
        it. Return an idempotent callback that unregisters that class.
        """
        assert_resolver_type_valid(resolver_type)

        def unregister() -> None:
            try:
                self._resolver_types.remove(resolver_type)
            except ValueError:
                pass

        unregister()
        self._resolver_types.insert(0, resolver_type)
        return unregister

    def clear(self) -> None:
        """Remove all registered resolver classes from this registry."""
        self._resolver_types = []
