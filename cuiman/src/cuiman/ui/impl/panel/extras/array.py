#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Any, Callable, Optional, TypeVar

import panel as pn
import param

from ..util import ArrayTextConverter

pn.extension()

T = TypeVar("T")


class ArrayWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    # TODO: check: better reuse `value` from base class
    value = param.List(default=[])

    def __init__(
        self,
        value: list,
        converter: ArrayTextConverter,
        separator: str | None = ",",
        name: str = "",
        description: str | None = None,
        **params,
    ):
        super().__init__(name="", **params)

        self.value = value
        self._converter = converter
        self._separator = separator

        # --- UI components

        initial_text = converter.format_array(value, sep=separator)
        sep_text = (
            "space or newline"
            if not separator or not separator.strip()
            else f"{separator!r}"
        )
        self._text = pn.widgets.TextAreaInput(
            value=initial_text,
            cols=16,
            rows=1,
            name=name,
            description=description or f"Use {sep_text} as separator.",
        )
        self._text.param.watch(self._on_text_value_change, "value")

        # --- value <-> internal

    def _on_text_value_change(self, event):
        assert isinstance(event.new, str)
        text = event.new
        try:
            value = self._converter.parse_array(text, sep=self._separator)
            if value != self.value:
                self.value = value
        except ValueError as e:
            self.error_message = f"{e}."

    # --- rendering

    def __panel__(self):
        return pn.Column(self._text)


# TODO: This is an experimental construction site. Don't use ArrayEditor yet.
class ArrayEditor(pn.widgets.WidgetBase, pn.custom.PyComponent):
    value = param.List(default=[])

    def __init__(
        self,
        value: list,
        value_factory: Callable[[], Any],
        item_editor: pn.widgets.WidgetBase,
        **params,
    ):
        super().__init__(**params)

        self.value = value
        self._value_factory = value_factory
        self._item_editor = item_editor

        self._selected_index: Optional[int] = None

        # --- UI components

        self._list = pn.widgets.Select(options=self._format_options(), size=5)
        self._add_btn = pn.widgets.Button(name="+", width=20)
        self._remove_btn = pn.widgets.Button(name="-", width=20)
        self._apply_btn = pn.widgets.Button(name="Apply", button_type="primary")

        # --- wiring

        self._list.param.watch(self._on_select, "value")
        self._add_btn.on_click(self._on_add)
        self._remove_btn.on_click(self._on_remove)
        self._apply_btn.on_click(self._on_apply)

        self.param.watch(self._on_value, "value")

        # --- layout

        left = pn.Column(
            self._list,
            pn.Row(self._add_btn, self._remove_btn),
            width=200,
        )

        right = pn.Column(
            self._item_editor,
            self._apply_btn,
        )

        self._panel = pn.Row(left, right)

        # initial sync
        self._sync_from_value()

    # --- value <-> internal

    def _sync_from_value(self):
        self._list.options = self._format_options()

    def _on_value(self, _event):
        self._sync_from_value()

    # --- list handling

    def _format_options(self):
        return {str(i): i for i in range(len(self.value))}

    def _on_select(self, event):
        self._selected_index = event.new
        if self._selected_index is not None:
            self._item_editor.value = self.value[self._selected_index]

    # --- actions

    def _on_add(self, _):
        new_item = self._value_factory()
        self.value = [*self.value, new_item]
        self._list.options = self._format_options()

    def _on_remove(self, _):
        if self._selected_index is None:
            return

        self.value = [v for i, v in enumerate(self.value) if i != self._selected_index]

        self._selected_index = None
        self._list.value = None
        self._list.options = self._format_options()

    def _on_apply(self, _):
        if self._selected_index is None:
            return

        updated = list(self.value)
        updated[self._selected_index] = self._item_editor.value
        self.value = updated

    # --- rendering

    def __panel__(self):
        return self._panel
