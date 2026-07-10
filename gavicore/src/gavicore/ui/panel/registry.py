#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from gavicore.ui import FieldFactoryRegistry

from .field import PanelField


class PanelFieldFactoryRegistry(FieldFactoryRegistry[PanelField]):
    """A registry for factories that create instances
    of a [PanelField][PanelField]."""

    @classmethod
    def create_default(cls) -> "PanelFieldFactoryRegistry":
        """Create an instance of this registry configured
        to produce a default set of widgets."""

        from .factory import DefaultPanelFieldFactory

        registry = PanelFieldFactoryRegistry()
        registry.register(DefaultPanelFieldFactory())
        return registry
