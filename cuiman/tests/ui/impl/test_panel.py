#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from cuiman.ui.impl.panel import create_field_builder
from cuiman.ui import FieldMeta
from gavicore.models import Schema


# noinspection PyMethodMayBeStatic
class PanelFieldBuilderTest(TestCase):
    def test_empty_schema(self):
        builder = create_field_builder()
        with pytest.raises(
            ValueError, match="no factory found for creating a UI for field 'root'"
        ):
            builder.create_field(_meta_from_schema({}))


def _meta_from_schema(d: dict) -> FieldMeta:
    return FieldMeta.from_schema("root", Schema(**d))
