#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, Literal, TypeAlias

import fsspec
import panel as pn
import param

from gavicore.ui.providers.panel.widgets.path import FilesystemPathInput


def _make_header(title: str, level: int) -> pn.viewable.Viewable:
    tag = f"h{level}"
    return pn.pane.HTML(f"<{tag} style='margin:0'>{title}</{tag}>")


def _make_divider() -> pn.viewable.Viewable:
    return pn.layout.Divider(margin=(-6, 0, 0, 6), sizing_mode="stretch_width")


# noinspection PyPep8Naming
def PanelHeader(
    *,
    title: str = "",
    level: int = 3,
    action: pn.viewable.Viewable | None = None,
) -> pn.viewable.Viewable:
    """A simple panel header."""
    header = pn.FlexBox(
        _make_header(title, level),
        *((action,) if action is not None else ()),
        align_items="center",
        justify_content="space-between",
        flex_wrap="nowrap",
        sizing_mode="stretch_width",
    )
    return pn.Column(
        header,
        _make_divider(),
        sizing_mode="stretch_width",
    )


# noinspection PyPep8Naming
def Panel(
    *content: pn.viewable.Viewable,
    title: str = "",
    level: int | None = None,
    indent: int | None = None,
    action: pn.viewable.Viewable | None = None,
) -> pn.layout.Panel:
    """A simple panel."""
    min_level = 3
    level_ = level or min_level
    return pn.Column(
        PanelHeader(title=title, level=level_, action=action),
        *content,
        sizing_mode="stretch_width",
        margin=(
            0,
            0,
            0,
            indent if indent is not None else max(0, 12 * (level_ - min_level)),
        ),
    )


class ClosablePanel(pn.viewable.Viewer):
    """A panel that can be closed."""

    title = param.String()
    visible = param.Boolean(default=True)
    level = param.Integer(default=None, allow_None=True)
    indent = param.Integer(default=None, allow_None=True)
    content = param.ClassSelector(class_=pn.viewable.Viewable, allow_refs=False)
    on_close = param.Callable(allow_None=True)

    def __init__(self, **params):
        super().__init__(**params)
        self._close_button = pn.widgets.ButtonIcon(size="1em", icon="x")
        self._close_button.on_click(self._on_close_clicked)
        self.param.watch(self._on_visible_change, "visible")

    @property
    def closed(self):
        return not self.visible

    def open(self):
        self.visible = True

    def close(self):
        self.visible = False

    def __panel__(self):
        panel = Panel(
            self.content,
            title=self.title if self.title else "",
            action=self._close_button,
            level=self.level,
            indent=self.indent,
        )
        panel.visible = pn.bind(lambda v: v, self.param.visible)
        return panel

    def _on_visible_change(self, _e):
        if self.on_close is not None and not self.visible:
            self.on_close()

    def _on_close_clicked(self, _e):
        self.close()


FileAction: TypeAlias = Callable[[fsspec.AbstractFileSystem, str], None]


class FilePanel(pn.viewable.Viewer):
    """
    A file panel comprises a `FilesystemPathInput` and has an optional
    action component to perform some action on the selected path.
    """

    def __init__(
        self,
        *,
        title: str,
        path: str,
        action_label: str,
        action_callback: FileAction,
        path_label: str = "Path",
        path_must_exist: bool = False,
        path_type: Literal["file", "directory"] = "file",
        on_close: Callable[[], None] | None = None,
        level: int | None = None,
        indent: int | None = None,
        **params,
    ):
        super().__init__(**params)
        self._action_button = pn.widgets.Button(name=action_label)
        self._action_button.on_click(self._on_action_click)
        self._action_callback = action_callback
        self._path_input = FilesystemPathInput(
            name=path_label or "",
            value=path,
            must_exist=path_must_exist,
            mode=path_type,
            action=self._action_button,
        )
        self._panel = ClosablePanel(
            title=title,
            content=self._path_input,
            on_close=on_close,
            level=level,
            indent=indent,
        )
        self._path_input.param.watch(self._on_path_error_change, "error")
        self._action_button.disabled = bool(self._path_input.error)

    @property
    def path(self) -> str:
        return self._path_input.value

    @path.setter
    def path(self, value: str):
        self._path_input.value = value

    @property
    def ok(self) -> bool:
        return not bool(self._path_input.error)

    @property
    def panel(self) -> ClosablePanel:
        return self._panel

    def __panel__(self):
        return self._panel

    def _on_path_error_change(self, _e):
        self._action_button.disabled = bool(self._path_input.error)

    def _on_action_click(self, _e):
        filesystem = self._path_input.filesystem
        path = self._path_input.value
        try:
            self._action_callback(filesystem, path)
        except Exception as e:
            self._path_input.error = str(e)
        # Autoclose, if not error:
        if self.ok:
            self.panel.close()


class FileOpenPanel(FilePanel):
    """
    A file panel used to select existing files and to perform a read-only action
    on the selected path.
    """

    def __init__(
        self,
        *,
        title: str,
        path: str,
        path_label: str,
        action_label: str,
        action_callback: FileAction,
        on_close: Callable[[], None] | None = None,
        level: int | None = None,
        indent: int | None = None,
        **params,
    ):
        super().__init__(
            path=path,
            title=title,
            path_label=path_label,
            path_must_exist=True,
            path_type="file",
            action_label=action_label,
            action_callback=action_callback,
            on_close=on_close,
            level=level,
            indent=indent,
            **params,
        )


class FileSavePanel(FilePanel):
    """
    A file panel used to select files and to perform a write-action
    on the selected path.
    """

    def __init__(
        self,
        *,
        title: str,
        path: str,
        path_label: str,
        action_label: str,
        action_callback: FileAction,
        on_close: Callable[[], None] | None = None,
        level: int | None = None,
        indent: int | None = None,
        **params,
    ):
        super().__init__(
            path=path,
            title=title,
            path_label=path_label,
            path_must_exist=False,
            path_type="file",
            action_label=action_label,
            action_callback=action_callback,
            on_close=on_close,
            level=level,
            indent=indent,
            **params,
        )
