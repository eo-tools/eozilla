#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from cuiman.ui import FieldMeta
from cuiman.ui.impl.panel import PanelFormFactory
from gavicore.models import Schema

from .schema2ui import load_schemas


# noinspection PyMethodMayBeStatic
class PanelFormFactoryTest(TestCase):
    def test_schemas(self):
        factory = PanelFormFactory()
        schemas = load_schemas()
        for path, schema in schemas:
            try:
                factory.create_form(_meta_from_schema(schema))
            except Exception as e:
                import traceback

                print(80 * "-")
                traceback.print_exc()
                print(80 * "-")
                self.fail(
                    f"Exception for schema {path.name!r}: {type(e).__name__}: {e}"
                )

    def test_empty_schema(self):
        factory = PanelFormFactory()
        with pytest.raises(
            ValueError, match="no factory found for creating a UI for field 'root'"
        ):
            factory.create_form(_meta_from_schema({}))


def _meta_from_schema(schema: Schema | dict) -> FieldMeta:
    return FieldMeta.from_schema(
        "root", schema if isinstance(schema, Schema) else Schema(**schema)
    )
