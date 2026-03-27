#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


from cuiman.ui import FieldFactoryRegistry, FormFactory

from .factories import PanelListPanelFactory, PanelWidgetFieldFactory


def create_field_builder() -> FormFactory:
    """
    Create a new builder for fields that create views
    using [Panel](https://panel.holoviz.org/) UI library.
    """
    registry = FieldFactoryRegistry(
        PanelWidgetFieldFactory(),
        PanelListPanelFactory(),
    )
    return FormFactory(registry)
