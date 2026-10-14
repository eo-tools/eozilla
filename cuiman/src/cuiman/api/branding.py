#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Public branding settings for a Cuiman-launched browser app."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AppEmojiIcon(BaseModel):
    """A header icon rendered as emoji text."""

    model_config = ConfigDict(extra="forbid")

    emoji: str = Field(strict=True, min_length=1)
    """Emoji text to display in the app header."""


class AppImageIcon(BaseModel):
    """A header icon loaded from an image URL."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(strict=True, min_length=1)
    """Image URL; relative paths resolve against the browser-visible app URL."""


class AppBranding(BaseModel):
    """Optional branding overrides, separate from processing-service settings.

    Omitted or ``None`` fields use the browser app's defaults. Asset URLs are
    serialized unchanged: use ``./logo.svg`` for an asset served alongside the
    app, including behind a Jupyter Server Proxy prefix. Supplying a URL does
    not publish a local file. No files are loaded implicitly.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, strict=True, min_length=1)
    """Title used in the browser tab and app header."""

    favicon: str | None = Field(default=None, strict=True, min_length=1)
    """URL of the browser tab icon."""

    icon: AppEmojiIcon | AppImageIcon | None = None
    """Header icon with exactly one of ``emoji`` or ``url``."""

    @classmethod
    def from_file(cls, path: str | Path) -> "AppBranding":
        """Load a JSON branding object from an explicitly selected UTF-8 file.

        The object contains ``title``, ``favicon``, and/or ``icon`` directly.
        Relative asset URLs remain relative to the browser app, not this file.
        ``~`` is expanded. Filesystem errors and validation errors propagate.
        """
        return cls.model_validate_json(
            Path(path).expanduser().read_text(encoding="utf-8")
        )
