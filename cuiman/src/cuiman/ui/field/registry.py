#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TYPE_CHECKING, Callable

from .meta import FieldMeta

if TYPE_CHECKING:
    from .factory import FieldFactory


class FieldFactoryRegistry:
    """A registry of field factories."""

    def __init__(self, *factories: "FieldFactory"):
        self._factories = set(factories)

    @property
    def factories(self) -> set["FieldFactory"]:
        """The factories registered in this registry."""
        return set(self._factories)

    def register(self, factory: "FieldFactory") -> Callable[[], None]:
        """Register a given factory."""

        def _unregister():
            self.unregister(factory)

        self._factories.add(factory)
        return _unregister

    def unregister(self, factory: "FieldFactory") -> None:
        """Unregister a given factory."""
        self._factories.discard(factory)

    def find(self, meta: FieldMeta) -> "FieldFactory | None":
        """Find a factory for the given field metadata."""
        max_score: int = 0
        best_factory: FieldFactory | None = None
        for f in self._factories:
            s = max(0, f.get_score(meta))
            if s > max_score:
                max_score = s
                best_factory = f
        return best_factory
