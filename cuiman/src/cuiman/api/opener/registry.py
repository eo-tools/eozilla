#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, TypeAlias

from .opener import JobResultOpener, assert_opener_type_valid

JobResultOpenerType: TypeAlias = type[JobResultOpener]


class JobResultOpenerRegistry:
    """A simple registry for job result openers."""

    def __init__(self):
        self._opener_types: list[JobResultOpenerType] = []

    @classmethod
    def create_default(cls) -> "JobResultOpenerRegistry":
        """Create a registry that includes default job result openers."""
        from .impl.gpd import GeopandasDataFrameOpener
        from .impl.pd import PandasDataFrameOpener
        from .impl.xr import XarrayDatasetOpener

        registry = JobResultOpenerRegistry()
        registry.register(GeopandasDataFrameOpener)
        registry.register(PandasDataFrameOpener)
        registry.register(XarrayDatasetOpener)
        return registry

    @property
    def opener_types(self) -> tuple[JobResultOpenerType, ...]:
        """The tuple of registered job result openers."""
        return tuple(self._opener_types)

    def register(self, opener_type: JobResultOpenerType) -> Callable[[], None]:
        """Register a job result opener.

        Args:
            opener_type: The type of the opener to be registered.

        Returns:
            A function that can be called to unregister the opener.
        """
        assert_opener_type_valid(opener_type)

        def unregister():
            try:
                self._opener_types.remove(opener_type)
            except ValueError:
                pass

        # Remove an already registered opener type
        unregister()

        # Insert at the beginning so that openers
        # added last are used first.
        self._opener_types.insert(0, opener_type)
        return unregister

    def clear(self) -> None:
        """Clears the registry.
        Removes registered all job result openers.
        """
        self._opener_types = []
