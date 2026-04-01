#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn
import io
import contextlib
import traceback

pn.extension()


class DebugHelper:
    _buffer = []
    _panel = pn.pane.Markdown("")

    @classmethod
    def print(cls, *args, end="\n"):
        """Print something."""
        cls._print(*args, end)

    @classmethod
    def _print(cls, *args):
        msg = " ".join(str(a) for a in args)
        cls._buffer.append(msg)
        cls._update_panel()

    @classmethod
    def _update_panel(cls):
        cls._panel.object = "".join(cls._buffer[-1000:])  # keep last N lines

    @classmethod
    def panel(cls):
        """The underlying panel."""
        return cls._panel

    @classmethod
    def show(cls):
        """Call for standalone display."""
        return pn.Column("### Debug Output", cls._panel)

    @classmethod
    def capture(cls, func, *args, **kwargs):
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
            cls.print(output.strip())

        return result

    @classmethod
    def clear(cls):
        """Clear all panel contents."""
        cls._buffer.clear()
        cls._update_panel()
