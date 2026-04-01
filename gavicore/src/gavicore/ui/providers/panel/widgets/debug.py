#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import contextlib
import io
import traceback

import panel as pn

pn.extension()


class DebugPanel(pn.widgets.WidgetBase, pn.custom.PyComponent):
    """
    Replacement for `print()` to be used from Panel UI code.

    Panel seem to swallow all console output and IPython.display
    outputs while a Panel viewable is showing.
    """

    _instance: "DebugPanel"

    @classmethod
    def instance(cls) -> "DebugPanel":
        if not hasattr(cls, "_instance"):
            cls._instance = DebugPanel()
        return cls._instance

    def __init__(self, **params):
        super().__init__(**params)
        self._buffer = []
        self._panel = pn.pane.Markdown("")

    def __panel__(self):
        return self._panel

    def print(self, *args, end="\n"):
        """Print something."""
        self._print(*args, end)

    def capture(self, func, *args, **kwargs):
        """Capture stdout + exceptions."""
        buffer = io.StringIO()
        # noinspection PyBroadException
        try:
            with contextlib.redirect_stdout(buffer):
                result = func(*args, **kwargs)
        except Exception:
            buffer.write(traceback.format_exc())
            result = None

        output = buffer.getvalue()
        if output:
            self.print(output.strip())

        return result

    def clear(self):
        """Clear all panel contents."""
        self._buffer.clear()
        self._update_panel()

    def _print(self, *args):
        msg = " ".join(str(a) for a in args)
        self._buffer.append(msg)
        self._update_panel()

    def _update_panel(self):
        self._panel.object = "".join(self._buffer[-1000:])  # keep last N lines
