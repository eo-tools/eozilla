#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from cuiman.ui import FieldMeta
from cuiman.ui.impl.panel import PanelFormFactory
from gavicore.models import Schema


# noinspection PyMethodMayBeStatic
class PanelFormFactoryTest(TestCase):
    def test_empty_schema(self):
        factory = PanelFormFactory()
        with pytest.raises(
            ValueError, match="no factory found for creating a UI for field 'root'"
        ):
            factory.create_form(_meta_from_schema({}))


def _meta_from_schema(d: dict) -> FieldMeta:
    return FieldMeta.from_schema("root", Schema(**d))
