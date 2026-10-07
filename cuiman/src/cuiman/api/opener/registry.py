#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, TypeAlias

from .opener import JobResultOpener, assert_opener_type_valid

JobResultOpenerType: TypeAlias = type[JobResultOpener]
"""An opener class registered for fresh instances during resource dispatch."""


class JobResultOpenerRegistry:
    """Choose which reader classes dispatch tries and in what order.

    Later registrations take priority, allowing application readers to precede
    built-ins. The registry stores classes rather than live readers or operation
    state, and client configuration keeps a registry per concrete config class.
    """

    def __init__(self):
        self._opener_types: list[JobResultOpenerType] = []

    @classmethod
    def create_default(cls) -> "JobResultOpenerRegistry":
        """Supply built-in image, dataset, and table readers for client defaults.

        Optional dependencies are checked when dispatch considers each reader.
        """
        from .impl import (
            GeopandasDataFrameOpener,
            ImageOpener,
            PandasDataFrameOpener,
            XarrayDatasetOpener,
        )

        registry = JobResultOpenerRegistry()
        registry.register(GeopandasDataFrameOpener)
        registry.register(PandasDataFrameOpener)
        registry.register(XarrayDatasetOpener)
        # Prefer Pillow for images before the generic dataset opener.
        registry.register(ImageOpener)
        return registry

    @property
    def opener_types(self) -> tuple[JobResultOpenerType, ...]:
        """Return a snapshot of reader classes in the order dispatch tries them."""
        return tuple(self._opener_types)

    def register(self, opener_type: JobResultOpenerType) -> Callable[[], None]:
        """Give an application reader priority over previously registered readers.

        Registering an existing class moves it to the front without duplication.

        Args:
            opener_type: The type of the opener to be registered.

        Returns:
            An idempotent function that unregisters the opener, useful for
            temporary registrations and test cleanup.
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
        """Remove all reader classes to build a configuration from an empty registry."""
        self._opener_types = []
