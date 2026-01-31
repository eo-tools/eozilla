#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from collections.abc import Iterable

import panel as pn
import param

from .x_menu_item import XMenuItemOptions, XMenuItem

MENU_WIDTH = 150

XMenuItemLike = XMenuItem | XMenuItemOptions | pn.viewable.Viewable | str


class XMenu(pn.viewable.Viewer):
    open = param.Boolean(default=False)

    def __init__(
        self,
        label: str,
        items: Iterable[XMenuItemLike],
        description: str | None = None,
        **params,
    ):
        super().__init__(**params)

        self.label = label
        self.button = pn.widgets.Button(description=description)
        self.button.on_click(lambda _: self._toggle_open())
        self._set_menu_button_name()

        self.items = []
        self.menu = pn.Column(
            visible=False,
            width=MENU_WIDTH,
            sizing_mode="fixed",
        )

        self.add_items(*items)

    def __panel__(self):
        return pn.Column(
            self.button,
            self.menu,
            styles={
                "position": "relative",
                "overflow": "visible",
                "top": "100%",
                "left": "0",
                "z-index": "1000",
            },
        )

    def add_items(self, *items: XMenuItemLike):
        for item in items:
            if isinstance(item, (str, dict)):
                item = XMenuItem(item, _close_menu=self.close_menu)
            self.items.append(item)
            self.menu.append(item)

    def open_menu(self):
        self._set_open(True)

    def close_menu(self):
        self._set_open(False)

    def _set_open(self, value: bool):
        self.open = value
        self.menu.visible = value
        self._set_menu_button_name()

    def _toggle_open(self):
        self._set_open(not self.open)

    def _set_menu_button_name(self):
        caret = "▴" if self.open else "▾"
        self.button.name = f"{self.label}   {caret}"
