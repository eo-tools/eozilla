#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import panel as pn
import pytest

from s2gos_client.gui.component import Component, JsonDateCodec, WidgetComponent


class ComponentTest(TestCase):
    def test_defaults(self):
        widget = pn.widgets.TextInput(name="Test", value="output.zarr")
        component = Component(widget)
        self.assertIs(widget, component.viewable)
        with pytest.raises(NotImplementedError):
            component.get_value()
        with pytest.raises(NotImplementedError):
            component.set_value(None)
        with pytest.raises(NotImplementedError):
            component.watch_value(lambda event: None)


class WidgetComponentTest(TestCase):
    def test_basics(self):
        widget = pn.widgets.TextInput(name="Test", value="output.zarr")
        component = WidgetComponent(widget)
        self.assertIs(widget, component.widget)
        self.assertIs(widget, component.viewable)
        self.assertEqual("output.zarr", component.get_json_value())
        self.assertEqual("output.zarr", component.get_value())

    def test_with_codec(self):
        json_codec = JsonDateCodec()
        value = json_codec.from_json("2025-06-07")
        widget = pn.widgets.DatePicker(name="Test", value=value)
        component = WidgetComponent(widget, json_codec=json_codec)
        self.assertEqual("2025-06-07", component.get_json_value())
        self.assertEqual(value, component.get_value())
        component.set_json_value("2025-06-08")
        self.assertEqual("2025-06-08", component.get_json_value())
        self.assertEqual(json_codec.from_json("2025-06-08"), component.get_value())

    def test_can_watch(self):
        widget = pn.widgets.TextInput(name="Test", value="output.zarr")
        component = WidgetComponent(widget)

        last_value = None

        def on_value_change(event):
            nonlocal last_value
            last_value = event.new

        component.watch_value(on_value_change)
        component.set_json_value("output.nc")

        self.assertEqual("output.nc", last_value)
        self.assertEqual("output.nc", component.get_json_value())
