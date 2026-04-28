#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import panel as pn

from gavicore.models import Schema
from gavicore.ui import FieldContext, FieldGenerator, FieldMeta
from gavicore.ui.providers.panel.factory import PanelFieldFactory, _FileDropperCodec
from gavicore.ui.providers.panel.widgets.labeled import LabeledWidget
from gavicore.ui.vm import AnyViewModel, PrimitiveViewModel, SelectiveViewModel


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

    def test_create_field_for_discriminator(self):
        generator = FieldGenerator()
        generator.register_field_factory(PanelFieldFactory())
        field = generator.generate_field(
            _meta_from_schema(
                {
                    "oneOf": [
                        {"$ref": "#/$defs/A"},
                        {"$ref": "#/$defs/B"},
                    ],
                    "discriminator": {
                        "propertyName": "t",
                    },
                    "$defs": {
                        "A": {
                            "type": "object",
                            "properties": {
                                "t": {"type": "string"},
                                "a": {"type": "integer"},
                            },
                        },
                        "B": {
                            "type": "object",
                            "properties": {
                                "t": {"type": "string"},
                                "b": {"type": "integer"},
                            },
                        },
                    },
                }
            )
        )
        self.assertIsInstance(field.view, LabeledWidget)
        self.assertIsInstance(field.view.inner_viewable, pn.layout.Tabs)
        self.assertIsInstance(field.view_model, SelectiveViewModel)

        self.assertEqual({"t": "A", "a": 0}, field.view_model.value)
        tabs = field.view.inner_viewable
        assert isinstance(tabs, pn.layout.Tabs)
        tabs.active = 1
        self.assertEqual({"t": "B", "b": 0}, field.view_model.value)

    def test_create_field_for_combinations(self):
        self.assert_create_field_for_combinations("oneOf")
        self.assert_create_field_for_combinations("anyOf")
        self.assert_create_field_for_combinations("allOf")

    def assert_create_field_for_combinations(self, combination_op: str):
        generator = FieldGenerator()
        generator.register_field_factory(PanelFieldFactory())

        field = generator.generate_field(_meta_from_schema({combination_op: []}))
        self.assertIsInstance(field.view_model, AnyViewModel)

        field = generator.generate_field(
            _meta_from_schema({combination_op: [{"type": "string"}]})
        )
        self.assertIsInstance(field.view_model, PrimitiveViewModel)


def _ctx_from_schema(schema: Schema | dict) -> FieldContext:
    generator = FieldGenerator()
    generator.register_field_factory(PanelFieldFactory())
    return FieldContext(generator=generator, meta=_meta_from_schema(schema))


def _meta_from_schema(schema: Schema | dict) -> FieldMeta:
    return FieldMeta.from_schema(
        "root", schema if isinstance(schema, Schema) else Schema(**schema)
    )


def test_json_file_dropper_codec():
    c = _FileDropperCodec()
    assert c.to_json(None) is None
    assert c.from_json(None) is None
    assert c.to_json({}) == ""
    assert c.from_json("") == {}
    assert c.to_json({"README.txt": "¡Adios!"}) == "wqFBZGlvcyE="
    assert c.from_json("wqFBZGlvcyE=") == {"bytes.bin": b"\xc2\xa1Adios!"}
    assert c.to_json({"bytes.bin": b"\xc2\xa1Adios!"}) == "wqFBZGlvcyE="
