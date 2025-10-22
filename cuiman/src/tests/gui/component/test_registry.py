#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import panel as pn

from s2gos_client.gui.component import (
    Component,
    ComponentFactoryBase,
    ComponentFactoryRegistry,
    JsonSchemaDict,
    JsonValue,
)


class MockFactory(ComponentFactoryBase):
    def create_component(
        self, json_value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        return Component(pn.widgets.TextInput(value=json_value, name=title))


class ComponentFactoryRegistryTest(TestCase):
    def test_register_and_find(self):
        class Factory0(MockFactory):
            pass

        class Factory1(MockFactory):
            type = "string"

        class Factory2(MockFactory):
            type = "array"
            format = "bbox"

        registry = ComponentFactoryRegistry()

        factory = registry.find_factory(dict(type="string"))
        self.assertIsNone(factory)

        Factory0.register_in(registry)
        Factory2.register_in(registry)
        Factory1.register_in(registry)

        factory = registry.find_factory(dict())
        self.assertIsInstance(factory, Factory0)

        factory = registry.find_factory(dict(type="string"))
        self.assertIsInstance(factory, Factory1)

        factory = registry.find_factory(dict(type="array"))
        self.assertIsNone(factory)

        factory = registry.find_factory(dict(type="array", format="bbox"))
        self.assertIsInstance(factory, Factory2)
