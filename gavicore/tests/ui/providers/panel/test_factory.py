#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from gavicore.models import Schema
from gavicore.ui import FieldMeta
from gavicore.ui.providers.panel.factory import PanelFieldFactory


class PanelFieldFactoryTest(TestCase):
    def test_get_score_for_arrays(self):
        factory = PanelFieldFactory()
        for t in ("boolean", "integer", "number", "string"):
            self.assertEqual(
                5,
                factory.get_score(
                    _meta_from_schema({"type": "array", "items": {"type": t}})
                ),
            )
        self.assertEqual(
            10,
            factory.get_score(
                _meta_from_schema(
                    {"type": "array", "format": "bbox", "items": {"type": "number"}}
                )
            ),
        )

        self.assertEqual(1, factory.get_score(_meta_from_schema({"type": "array"})))
        self.assertEqual(
            1,
            factory.get_score(
                _meta_from_schema({"type": "array", "items": {"type": "object"}})
            ),
        )
        self.assertEqual(
            1,
            factory.get_score(
                _meta_from_schema(
                    {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "string"}},
                    }
                ),
            ),
        )


def _meta_from_schema(schema: Schema | dict) -> FieldMeta:
    return FieldMeta.from_schema(
        "root", schema if isinstance(schema, Schema) else Schema(**schema)
    )
