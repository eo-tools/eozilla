#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import panel as pn
import pytest

from s2gos_client.gui.component import (
    Component,
    ComponentFactoryBase,
    JsonSchemaDict,
    JsonValue,
)


class MockFactory(ComponentFactoryBase):
    def create_component(
        self, json_value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        return Component(pn.widgets.TextInput(value=json_value, name=title))


class MockRegistry:
    def __init__(self):
        self.registrations = []

    def register_factory(self, *args, **kwargs):
        self.registrations.append((args, kwargs))


class ComponentFactoryTest(TestCase):
    def test_get_score_type_and_format(self):
        class Factory2(MockFactory):
            type = "array"
            format = "bbox"

        f2 = Factory2()
        self.assertEqual(False, f2.accept(dict()))
        self.assertEqual(False, f2.accept(dict(type="integer")))
        self.assertEqual(False, f2.accept(dict(type="array")))
        self.assertEqual(True, f2.accept(dict(type="array", format="bbox")))
        self.assertEqual(False, f2.accept(dict(format="bbox")))

    def test_get_score_type_only(self):
        class Factory1(MockFactory):
            type = "string"

        f1 = Factory1()
        self.assertEqual(False, f1.accept(dict()))
        self.assertEqual(False, f1.accept(dict(type="integer")))
        self.assertEqual(True, f1.accept(dict(type="string")))
        self.assertEqual(False, f1.accept(dict(type="string", format="date")))
        self.assertEqual(False, f1.accept(dict(format="date")))

    def test_get_score_format_only(self):
        class Factory(MockFactory):
            format = "point"

        f = Factory()
        self.assertEqual(False, f.accept(dict()))
        self.assertEqual(False, f.accept(dict(format="bbox")))
        self.assertEqual(True, f.accept(dict(format="point")))
        self.assertEqual(False, f.accept(dict(type="integer", format="point")))
        self.assertEqual(False, f.accept(dict(type="number")))

    # noinspection PyMethodMayBeStatic,PyTypeChecker
    def test_register_in(self):
        class GoodFactory0(MockFactory):
            pass

        class GoodFactory1(MockFactory):
            type = "string"

        class GoodFactory2(MockFactory):
            type = "integer"

        class GoodFactory3(MockFactory):
            type = "boolean"
            format = "*"

            def accept(self, schema: JsonSchemaDict) -> bool:
                return schema.get("format") in ("bistate", "tristate")

        registry = MockRegistry()
        GoodFactory0.register_in(registry)
        GoodFactory1.register_in(registry)
        GoodFactory2.register_in(registry)
        GoodFactory3.register_in(registry)
        self.assertEqual(
            [
                {"format": None, "type": None},
                {"format": None, "type": "string"},
                {"format": None, "type": "integer"},
                {"format": "*", "type": "boolean"},
            ],
            [kwargs for _args, kwargs in registry.registrations],
        )
        self.assertIsInstance(registry.registrations[0][0][0], GoodFactory0)
        self.assertIsInstance(registry.registrations[1][0][0], GoodFactory1)
        self.assertIsInstance(registry.registrations[2][0][0], GoodFactory2)
        self.assertIsInstance(registry.registrations[3][0][0], GoodFactory3)

    # noinspection PyMethodMayBeStatic
    def test_raise_on_missing_accept(self):
        class FactoryWithoutOwnAccept(MockFactory):
            type = "string"
            format = "*"

        with pytest.raises(
            TypeError,
            match=(
                r"class FactoryWithoutOwnAccept must override method "
                r"ComponentFactoryBase\.accept\(\)"
            ),
        ):
            FactoryWithoutOwnAccept()

    # noinspection PyMethodMayBeStatic
    def test_raise_on_wrong_type(self):
        class FactoryWithWrongTypeName(MockFactory):
            type = "strong"

        with pytest.raises(
            ValueError,
            match=(
                "value of ComponentFactoryBase.type must be one of "
                "'boolean', 'integer', 'number', 'string', 'array', 'object', "
                "but was 'strong'"
            ),
        ):
            FactoryWithWrongTypeName()
