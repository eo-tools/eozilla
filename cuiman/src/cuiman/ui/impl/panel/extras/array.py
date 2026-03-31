#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable

import panel as pn
import param

from ..util import ArrayTextConverter

pn.extension()


class ArrayWidget(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """A text input or text area for editing array items."""

    value = param.List(default=[])

    def __init__(
        self,
        value: list,
        converter: ArrayTextConverter,
        separator: str | None = ",",
        name: str | None = None,
        description: str | None = None,
        **params,
    ):
        super().__init__(name="", **params)

        self.value = value
        self._converter = converter
        self._separator = separator

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

    def _on_text_value_change(self, event):
        assert isinstance(event.new, str)
        text = event.new
        try:
            value = self._converter.parse_array(text, sep=self._separator)
            if value != self.value:
                self.value = value
        except ValueError as e:
            self.error_message = f"{e}."

    def __panel__(self):
        return pn.Column(self._text)


class ArrayEditor(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """A simple editor for editing values of type list (arrays)."""

    value = param.List(default=[])

    def __init__(
        self,
        value: list[Any],
        item_value_factory: Callable[[], Any],
        item_editor_factory: Callable[[int, Any], pn.widgets.WidgetBase],
        **params,
    ):
        super().__init__(**params)
        self.value = value
        self._item_value_factory = item_value_factory
        self._item_editor_factory = item_editor_factory
        self._items_box = pn.Column(
            max_height=200,
            styles={"overflow-y": "auto", "gap": "0"},
        )
        add_btn = pn.widgets.ButtonIcon(
            icon="circle-plus",
            name="Add Item",
            size="1.5em",
        )
        add_btn.on_click(self._on_add_item)
        self._add_row = pn.Row(
            add_btn,
        )
        if self.name:
            panel = pn.Column(
                f"### {self.name}",
                pn.layout.Divider(margin=(-16, 0, 0, 8)),
                self._items_box,
                self._add_row,
            )
        else:
            panel = pn.Column(self._items_box, self._add_row)
        self._panel = panel
        self._update_item_rows()
        self.param.watch(self._on_value_change, "value")

    def _on_add_item(self, _e):
        self.value = self.value + [self._item_value_factory()]

    def _on_value_change(self, _e):
        self._update_item_rows()

    def _update_item_rows(self):
        # brute force
        self._items_box[:] = self._render_item_rows()

    def _render_item_rows(self):
        return [self._render_item_row(i, v) for i, v in enumerate(self.value)]

    def _render_item_row(self, index, value):
        def on_delete_item(_event):
            v = list(self.value)
            del v[index]
            self.value = v

        del_btn = pn.widgets.ButtonIcon(icon="x", size="1em")
        del_btn.on_click(on_delete_item)
        return pn.Row(
            self._render_item_editor(index, value),
            del_btn,
            styles={"gap": "0.5em"},
        )

    def _render_item_editor(self, index, value):
        def on_item_value_change(e):
            v = list(self.value)
            v[index] = e.new
            self.value = v

        item_editor = self._item_editor_factory(index, value)
        item_editor.param.watch(on_item_value_change, "value")
        return item_editor

    def __panel__(self):
        return self._panel
