#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import panel as pn

from s2gos_client.gui.component import ComponentContainer
from s2gos_common.models import InputDescription, Schema


class ComponentContainerTest(TestCase):
    def test_basics(self):
        container = ComponentContainer.from_input_descriptions(
            {
                "a_string": InputDescription(
                    title="String X",
                    description="A string",
                    schema=Schema(type="string"),
                )
            },
            {"a_string": "bert"},
        )
        self.assertIsInstance(container, ComponentContainer)
        components = container.get_components()
        self.assertIsInstance(components, list)
        self.assertEqual(1, len(components))
        component = components[0]
        self.assertIsInstance(component.viewable, pn.widgets.Widget)

        self.assertDictEqual({"a_string": "bert"}, container.get_json_values())
        self.assertEqual("bert", component.viewable.value)

        container.set_json_values({"a_string": "bibo"})
        self.assertDictEqual({"a_string": "bibo"}, container.get_json_values())
        self.assertEqual("bibo", component.viewable.value)
