#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from dataclasses import dataclass
from typing import Callable, Any, TypedDict, overload
import panel as pn

XMENU_ITEM_CSS = r"""
.xmenu-item .bk-btn {
  justify-content: flex-start !important;
  text-align: left !important;
}
"""
pn.extension(raw_css=[XMENU_ITEM_CSS])


@dataclass
class XMenuItemOptions(TypedDict, total=False):
    label: str
    disabled: bool | None
    autoclose: bool
    on_click: Callable | None
    button_params: dict[str, None] | None


class XMenuItem(pn.viewable.Viewer):
    @overload
    def __init__(
        self,
        options: XMenuItemOptions,
        _close_menu: Callable | None = None,
        **button_params: Any,
    ): ...
    @overload
    def __init__(
        self,
        label: str,
        disabled: bool = False,
        on_click: Callable | None = None,
        _close_menu: Callable | None = None,
        **button_params: Any,
    ): ...
    def __init__(
        self,
        options_or_label: XMenuItemOptions | str,
        disabled: bool | None = None,
        on_click: Callable | None = None,
        _close_menu: Callable | None = None,
        **button_params: Any,
    ):
        super().__init__()

        options: XMenuItemOptions
        if isinstance(options_or_label, str):
            options = {"label": options_or_label}
        else:
            options = options_or_label

        label = options.get("label")
        disabled = options.get("disabled", False) if disabled is None else disabled
        on_click = options.get("on_click") if on_click is None else on_click
        button_params = (
            options.get("button_params") if button_params is None else button_params
        )

        self.button = pn.widgets.Button(
            name=label,
            disabled=disabled,
            sizing_mode="stretch_width",
            **button_params,
        )
        self.button.css_classes = ["xmenu-item"]  # doesn't work  :(
        self.button.margin = (1, 10)

        if on_click:
            self.button.on_click(on_click)

        if _close_menu:
            self.button.on_click(lambda _: _close_menu())

    def __panel__(self):
        return self.button
