#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
import pathlib

import fsspec
import panel as pn
import param


class FilesystemPathInput(pn.custom.PyComponent, pn.widgets.WidgetBase):
    """
    A Panel widget providing shell-style path autocomplete via fsspec.

    Args:
        value:
            The confirmed, resolved path. Updated only on Enter or explicit confirm.
        protocol: A `fsspec` filesystem protocol.
            Defaults to `"file"`, the local filesystem.
        storage_options: Filesystem-specific storage options.
            Defaults to `"file"`, the local filesystem.
        mode: The mode:
            - `"file"` autocomplete includes files and directories
            - `"directory"` — autocomplete includes directories only
        must_exist:
            If True, `value` is only updated when the path exists on the filesystem.
            If False, non-existing paths are accepted (useful for save-as / new dirs).
        placeholder:
            Placeholder text shown in the input.
    """

    value = param.String(default="", doc="Confirmed resolved path")
    protocol = param.String(default="file", doc="Filesystem protocol", allow_None=True)
    storage_options = param.Dict(
        default=None, doc="Filesystem storage options", allow_None=True
    )
    mode = param.ObjectSelector(default="file", objects=["file", "directory"])
    must_exist = param.Boolean(default=True)
    visible = param.Boolean(default=True)
    placeholder = param.String(default="Enter path...")
    description = param.String(default=None, allow_None=True)
    error = param.String(default=None, allow_None=True)
    action = param.ClassSelector(
        default=None,
        class_=(pn.widgets.Button, pn.widgets.ButtonIcon),
        allow_None=True,
        allow_refs=False,
    )

    def __init__(self, **params):
        name = params.pop("name", None) or ""
        super().__init__(name=name, **params)

        self._fs = fsspec.filesystem(
            self.protocol or "file", **(self.storage_options or {})
        )
        self._local = self._is_local_fs(self._fs)
        self._separator = os.sep if self._local else "/"
        self._case_sensitive = not (self._local and os.name == "nt")
        self._old_completions: list[str] = []

        self._autocomplete = pn.widgets.AutocompleteInput(
            name=self.name,
            value=self.value,
            placeholder=self.placeholder,
            restrict=False,
            min_characters=0,
            case_sensitive=self._case_sensitive,
            sizing_mode="stretch_width",
            stylesheets=[
                """
                :host input {
                    font-family: 'JetBrains Mono', 'Fira Mono', monospace;
                    font-size: 13px;
                }
            """
            ],
        )
        self._error_pane = pn.pane.HTML(
            "",
            stylesheets=[
                """
                :host {
                    color: #e05252;
                    font-size: 12px;
                    font-family: monospace;
                    min-height: 16px;
                }
            """
            ],
            visible=False,
        )

        # Sync
        self.param.watch(self._on_placeholder_change, "placeholder")
        self.param.watch(self._on_description_change, "description")

        # Keystroke → update completions
        self._autocomplete.param.watch(self._on_input_change, "value_input")

        # Enter / confirm → validate and set value
        self._autocomplete.param.watch(self._on_input_confirm, "value")

        # Value change → sync with autocomplete
        self.param.watch(self._on_value_change, "value")

        # Error change → render error
        self.param.watch(self._on_error_change, "error")

        self._validate_path(self.value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def filesystem(self) -> fsspec.AbstractFileSystem:
        return self._fs

    # ------------------------------------------------------------------
    # Panel rendering
    # ------------------------------------------------------------------

    def __panel__(self):
        if self.action is not None:
            content = pn.FlexBox(
                self._autocomplete,
                self.action,
                flex_direction="row",
                align_items="flex-end",
                justify_content="space-between",
                flex_wrap="nowrap",
                sizing_mode="stretch_width",
                margin=0,
            )
        else:
            content = self._autocomplete

        return pn.Column(
            content,
            self._error_pane,
            sizing_mode="stretch_width",
            margin=0,
            visible=self.visible,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_placeholder_change(self, event):
        self._autocomplete.placeholder = event.new

    def _on_description_change(self, event):
        self._autocomplete.description = event.new

    def _on_input_change(self, event):
        """Called on every keystroke — update autocomplete options."""
        new_completions = self._compute_completions(event.new)
        if new_completions:
            # Remember current completions
            self._old_completions = new_completions
        else:
            # AutocompleteInput resets value if new_completions is empty,
            # therefore we use the old ones here:
            new_completions = self._old_completions
        self._autocomplete.options = new_completions
        self.error = None

    def _on_input_confirm(self, event):
        """Called when user presses Enter — validate and update value."""
        raw_path = event.new.strip()
        if not raw_path:
            return
        self._validate_path(raw_path)

    def _on_value_change(self, event):
        if self._autocomplete.value != event.new:
            # Synchronize autocomplete with value
            self._autocomplete.value = event.new

    def _on_error_change(self, _event):
        is_error = bool(self.error)
        self._error_pane.visible = is_error
        self._error_pane.object = self.error or ""

    @classmethod
    def _is_local_fs(cls, fs: fsspec.AbstractFileSystem) -> bool:
        protocol = getattr(fs, "protocol", "file")
        if isinstance(protocol, (list, tuple)):
            protocol = protocol[0]
        return protocol == "file"

    def _resolve(self, prefix: str) -> str:
        """
        Resolve a prefix to an absolute path string.
        Handles:
          - empty string       → cwd
          - "~" / "~/.."      → expanded home
          - "." / "./foo"     → relative to cwd
          - "../foo"          → relative to cwd
          - absolute paths    → as-is
          - Windows drive paths like "C:\\..." or "C:/..."
        For remote filesystems, relative paths are returned unchanged.
        """
        if not self._local:
            return prefix  # remote fs: caller manages paths

        if not prefix:
            return str(pathlib.Path.cwd())

        p = pathlib.Path(prefix)

        # Expand ~ and ~user
        try:
            p = p.expanduser()
        except RuntimeError:
            pass

        # Resolve relative paths against cwd (don't resolve symlinks yet —
        # the path may not exist, e.g. during save-as)
        if not p.is_absolute():
            p = pathlib.Path.cwd() / p

        return str(p)

    def _compute_completions(self, prefix: str) -> list[str]:
        """Return fsspec-based path completions for the given prefix."""
        # noinspection PyBroadException
        try:
            fs = self._fs
            sep = self._separator

            # Expand and resolve the prefix to determine parent dir + stub
            if self._local:
                resolved = self._resolve(prefix)
                p = pathlib.Path(resolved)

                # If prefix ends with sep or is an existing dir → list inside it
                if prefix.endswith(("/", os.sep)) or (p.exists() and p.is_dir()):
                    parent = str(p)
                    stub = ""
                else:
                    parent = str(p.parent)
                    stub = p.name
            else:
                # Remote: simple string splitting
                if prefix.endswith(sep):
                    parent = prefix or sep
                    stub = ""
                else:
                    parts = prefix.rsplit(sep, 1)
                    parent = parts[0] + sep if len(parts) > 1 else sep
                    stub = parts[1] if len(parts) > 1 else prefix

            entries = fs.ls(parent, detail=True)
            results = []
            for entry in entries:
                entry_name = entry.get("name", "")
                entry_type = entry.get("type", "")

                # fsspec always returns forward slashes; normalize for local Windows
                if self._local and os.sep == "\\":
                    entry_name = entry_name.replace("/", "\\")

                basename = (
                    entry_name.rsplit(sep, 1)[-1] if sep in entry_name else entry_name
                )

                # Filter hidden files only when stub doesn't start with a dot
                if not stub.startswith(".") and basename.startswith("."):
                    continue

                if self._case_sensitive:
                    prefix_matches = basename.startswith(stub)
                else:
                    prefix_matches = basename.lower().startswith(stub.lower())
                if not prefix_matches:
                    continue

                # Build display path preserving the user's original prefix style
                if self._local:
                    display = str(pathlib.Path(parent) / basename)
                else:
                    display = entry_name

                if entry_type == "directory":
                    results.append(display + sep)
                elif self.mode == "file":
                    results.append(display)

            return sorted(results)
        except Exception:
            return []

    def _validate_path(self, raw_path: str):
        # Resolve to absolute path for local fs
        path = self._resolve(raw_path) if self._local else raw_path

        if self.must_exist:
            try:
                exists = self._fs.exists(path)
            except Exception as e:
                self.error = f"⚠ Error checking path: {e}"
                return

            if not exists:
                self.error = f"⚠ Path does not exist: {path}"
                return

            if self.mode == "directory" and not self._fs.isdir(path):
                self.error = f"⚠ Not a directory: {path}"
                return

            if self.mode == "file" and self._fs.isdir(path):
                self.error = f"⚠ Path is a directory, not a file: {path}"
                return

        self.error = None
        self.value = path
