#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from gavicore.models import Schema
from gavicore.ui import FieldMeta
from gavicore.ui.providers.panel import PanelField

from .schema2ui import load_schemas


# noinspection PyMethodMayBeStatic
class PanelFieldTest(TestCase):
    def test_with_all_schemas(self):
        # TODO: test type="discriminator"
        # TODO: test type="anyOf"
        # TODO: test type="allOf"
        # TODO: test type="oneOf"

        schemas = load_schemas()
        for path, schema in schemas:
            name = path.stem.replace("-", "_")
            try:
                PanelField.from_schema(name, schema)
            except Exception as e:
                import traceback

                print(80 * "-")
                traceback.print_exc()
                print(80 * "-")
                self.fail(
                    f"Exception for schema {path.name!r}: {type(e).__name__}: {e}"
                )

    def test_empty_schema(self):
        with pytest.raises(
            ValueError, match="no factory found for creating a UI for field 'root'"
        ):
            PanelField.from_meta(_meta_from_schema({}))


def _meta_from_schema(schema: Schema | dict) -> FieldMeta:
    return FieldMeta.from_schema(
        "root", schema if isinstance(schema, Schema) else Schema(**schema)
    )
