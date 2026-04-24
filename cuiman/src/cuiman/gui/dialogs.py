#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Callable, Literal, TypeAlias

import fsspec
import param
import panel as pn


from gavicore.ui.providers.panel.widgets.path import FilesystemPathInput


class InlineDialog(pn.viewable.Viewer):
    title = param.String()
    visible = param.Boolean(default=True)
    content = param.ClassSelector(class_=pn.viewable.Viewable, allow_refs=False)
    on_close = param.Callable(allow_None=True)

    def __init__(self, **params):
        super().__init__(**params)
        self._close_btn = pn.widgets.ButtonIcon(size="1em", icon="x")
        self._close_btn.on_click(self._on_close_clicked)
        self.param.watch(self._on_visible_change, "visible")

    @property
    def closed(self):
        return not self.visible

    def open(self):
        self.visible = True

    def close(self):
        self.visible = False

    def __panel__(self):
        header = pn.FlexBox(
            pn.pane.Markdown(object=f"{self.title}" if self.title else ""),
            self._close_btn,
            align_items="center",
            justify_content="space-between",
            flex_wrap="nowrap",
            sizing_mode="stretch_width",
        )
        return pn.Column(
            header,
            pn.layout.Divider(margin=(-20, 0, 0, 6)),
            self.content,
            sizing_mode="stretch_width",
            margin=0,
            visible=pn.bind(lambda v: v, self.param.visible),
        )

    def _on_visible_change(self, _e):
        if self.on_close is not None and not self.visible:
            self.on_close()

    def _on_close_clicked(self, _e):
        self.close()


FileAction: TypeAlias = Callable[[fsspec.AbstractFileSystem, str], None]


class FileDialog(pn.viewable.Viewer):
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
        self._dialog = InlineDialog(
            title=title,
            content=self._path_input,
            on_close=on_close,
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
    def dialog(self) -> InlineDialog:
        return self._dialog

    def __panel__(self):
        return self._dialog

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
            self.dialog.close()


class FileOpenDialog(FileDialog):
    def __init__(
        self,
        *,
        title: str,
        path: str,
        path_label: str,
        action_label: str,
        action_callback: FileAction,
        on_close: Callable[[], None] | None = None,
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
            **params,
        )


class FileSaveDialog(FileDialog):
    def __init__(
        self,
        *,
        title: str,
        path: str,
        path_label: str,
        action_label: str,
        action_callback: FileAction,
        on_close: Callable[[], None] | None = None,
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
            **params,
        )
