#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from gavicore.models import Schema
from gavicore.ui import (
    FieldBase,
    FieldMeta,
)
from gavicore.ui.vm import PrimitiveViewModel


class MyField(FieldBase):
    def _bind(self) -> None:
        self.bound = True


class FieldBaseTest(TestCase):
    def test_builder(self):
        meta = FieldMeta.from_schema(
            "threshold",
            Schema(
                **{
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                }
            ),
        )

        view_model = PrimitiveViewModel(meta)
        view = object()
        f = MyField(view_model, view)
        self.assertIs(view_model, f.view_model)
        self.assertIs(view, f.view)
        self.assertTrue(hasattr(f, "bound"))
        self.assertTrue(f.bound)
