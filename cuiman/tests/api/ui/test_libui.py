#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from .libui import (
    Checkbox,
    ListEditor,
    NullableView,
    NumberInput,
    Panel,
    TextInput,
    Switch,
    View,
    Slider,
    Select,
    TextArea,
)

# --- Test the mock component library Libui --------


class LibuiTest(TestCase):
    def test_text_area(self):
        self._assert_view(TextArea(value="# Abstract"), "# Abstract", "## Abstract\n")

    def test_text_input(self):
        self._assert_view(
            TextInput(value="/data/ds.zarr"), "/data/ds.zarr", "/data/ds.nc"
        )

    def test_number_input(self):
        self._assert_view(NumberInput(value=3.7), 3.7, 3.8)

    def test_slider(self):
        self._assert_view(Slider(value=10), 10, 20)

    def test_checkbox(self):
        self._assert_view(Checkbox(value=False), False, True)

    def test_switch(self):
        self._assert_view(Switch(value=False), False, True)

    def test_select(self):
        self._assert_view(Select(value="A", options=["A", "B"]), "A", "B")

    def test_list_editor(self):
        self._assert_view(ListEditor(value=[1, 2, 3]), [1, 2, 3], [1, 2, 3, 4])

    def test_panel(self):
        self._assert_view(
            Panel(children={"a": Switch(value=False), "b": Slider(value=50)}),
            {"a": False, "b": 50},
            {"a": True, "b": 40},
        )

    def test_nullable_view(self):
        self._assert_view(
            NullableView(value=None, child=NumberInput(value=137)), None, 137
        )

    def _assert_view(self, view: View, initial_value, other_value) -> View:
        self.assertEqual(initial_value, view.value)
        view.value = other_value
        self.assertEqual(other_value, view.value)

        change_count = 0

        def observe_view():
            nonlocal change_count
            change_count += 1

        view.watch(observe_view)
        view.value = initial_value
        self.assertEqual(1, change_count)
        view.value = initial_value
        self.assertEqual(1, change_count)
        view.value = other_value
        self.assertEqual(2, change_count)
        view.value = other_value
        self.assertEqual(2, change_count)
        view.value = initial_value
        self.assertEqual(3, change_count)
        self.assertEqual(initial_value, view.value)

        view.unwatch(observe_view)
        view.value = other_value
        self.assertEqual(3, change_count)

        return view
