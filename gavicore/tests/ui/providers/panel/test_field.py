#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from gavicore.models import Schema
from gavicore.ui import FieldMeta
from gavicore.ui.providers.panel import PanelField

from .schema2ui import load_schemas


# noinspection PyMethodMayBeStatic
class PanelFieldTest(TestCase):
    def test_with_all_schemas(self):
        # TODO: test type="discriminator"
        # TODO: test type="anyOf"

        schemas = load_schemas()
        for path, schema in schemas:
            name = path.stem.replace("-", "_")
            try:
                PanelField.from_schema(name, schema)
            except Exception as e:
                raise self.failureException(
                    f"Exception for schema from path {path}: {e}"
                ) from e


def _meta_from_schema(schema: Schema | dict) -> FieldMeta:
    return FieldMeta.from_schema(
        "root", schema if isinstance(schema, Schema) else Schema(**schema)
    )
