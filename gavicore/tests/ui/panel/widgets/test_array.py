#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from gavicore.ui.panel.widgets.array import ArrayEditor, ArrayWidget
from gavicore.util.text import TextConverter


class ArrayWidgetTest(TestCase):
    def test_value_change_updates_text(self):
        widget = ArrayWidget(
            value=[0.0, 0.0],
            array_converter=TextConverter.NumberArray(),
        )

        widget.value = [10.0, 20.0]

        self.assertEqual("10.0, 20.0", widget._text.value)

    def test_text_change_keeps_entered_text(self):
        widget = ArrayWidget(
            value=[0.0, 0.0],
            array_converter=TextConverter.NumberArray(),
        )

        widget._text.value = "10, 20"

        self.assertEqual([10.0, 20.0], widget.value)
        self.assertEqual("10, 20", widget._text.value)


class ArrayEditorTest(TestCase):
    def test_item_change_does_not_recreate_item_editor(self):
        editor = _number_pair_editor([[0.0, 0.0], [0.0, 0.0]])
        first_row = editor._items_box[0]
        first_item_editor = first_row[0]

        first_item_editor._text.value = "10, 20"

        self.assertEqual([[10.0, 20.0], [0.0, 0.0]], editor.value)
        self.assertIs(first_row, editor._items_box[0])
        self.assertIs(first_item_editor, editor._items_box[0][0])
        self.assertEqual([10.0, 20.0], first_item_editor.value)
        self.assertEqual("10, 20", first_item_editor._text.value)

    def test_external_value_change_recreates_item_editors(self):
        editor = _number_pair_editor([[0.0, 0.0], [0.0, 0.0]])
        first_row = editor._items_box[0]

        editor.value = [[10.0, 20.0]]

        self.assertEqual(1, len(editor._items_box))
        self.assertIsNot(first_row, editor._items_box[0])


def _number_pair_editor(value: list[list[float]]) -> ArrayEditor:
    def create_item_editor(_index: int, item_value: list[float]):
        return ArrayWidget(
            value=item_value,
            array_converter=TextConverter.NumberArray(),
        )

    return ArrayEditor(
        value=value,
        item_value_factory=lambda: [0.0, 0.0],
        item_editor_factory=create_item_editor,
    )
