#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from .libui import (
    Checkbox,
    Column,
    ListEditor,
    NullableWidget,
    NumberInput,
    Row,
    Select,
    Slider,
    Switch,
    TextArea,
    TextInput,
    View,
    Widget,
)

# --- Test the mock component library Libui --------


class LibuiTest(TestCase):
    def test_text_area(self):
        self._assert_widget(TextArea(value="# Abstract"), "# Abstract", "## Abstract\n")

    def test_text_input(self):
        self._assert_widget(
            TextInput(value="/data/ds.zarr"), "/data/ds.zarr", "/data/ds.nc"
        )

    def test_number_input(self):
        self._assert_widget(NumberInput(value=3.7), 3.7, 3.8)

    def test_slider(self):
        self._assert_widget(Slider(value=10), 10, 20)

    def test_checkbox(self):
        self._assert_widget(Checkbox(value=False), False, True)

    def test_switch(self):
        self._assert_widget(Switch(value=False), False, True)

    def test_select(self):
        self._assert_widget(Select(value="A", options=["A", "B"]), "A", "B")

    def test_list_editor(self):
        self._assert_widget(ListEditor(value=[1, 2, 3]), [1, 2, 3], [1, 2, 3, 4])

    def test_nullable_view(self):
        self._assert_widget(
            NullableWidget(value=None, child=NumberInput(value=137)), None, 137
        )

    def _assert_widget(self, widget: Widget, initial_value, other_value) -> View:
        self.assertEqual(initial_value, widget.value)
        widget.value = other_value
        self.assertEqual(other_value, widget.value)

        change_count = 0

        def observe_view():
            nonlocal change_count
            change_count += 1

        widget.watch(observe_view)
        widget.value = initial_value
        self.assertEqual(1, change_count)
        widget.value = initial_value
        self.assertEqual(1, change_count)
        widget.value = other_value
        self.assertEqual(2, change_count)
        widget.value = other_value
        self.assertEqual(2, change_count)
        widget.value = initial_value
        self.assertEqual(3, change_count)
        self.assertEqual(initial_value, widget.value)

        widget.unwatch(observe_view)
        widget.value = other_value
        self.assertEqual(3, change_count)
        self.assertEqual(other_value, widget.value)

        return widget

    def test_container(self):
        child_1 = Switch(value=False)
        child_2 = Slider(value=50)

        view = Column(children=[child_1, child_2])
        self.assertEqual([child_1, child_2], view.children)

        view = Row(children=[child_1, child_2])
        self.assertEqual([child_1, child_2], view.children)
