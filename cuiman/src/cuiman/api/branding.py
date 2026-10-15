#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Public branding settings for a Cuiman-launched browser app."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AppEmojiIcon(BaseModel):
    """A header icon rendered as emoji text."""

    model_config = ConfigDict(extra="forbid")

    emoji: str = Field(strict=True, min_length=1)
    """Emoji text to display in the app header."""


class AppImageIcon(BaseModel):
    """An image supplied by exactly one browser URL or Python-local file path."""

    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, strict=True, min_length=1)
    """Image URL; relative paths resolve against the browser-visible app URL."""

    path: Path | None = None
    """Local image file; relative paths resolve against Python's working directory."""

    @model_validator(mode="after")
    def validate_source(self) -> "AppImageIcon":
        """Require exactly one image source."""
        if (self.url is None) == (self.path is None):
            raise ValueError("Supply exactly one of 'path' or 'url'.")
        return self


class AppBranding(BaseModel):
    """Optional branding overrides, separate from processing-service settings.

    Omitted or ``None`` fields use the browser app's defaults. Use ``path`` for
    Python-local files and ``url`` for browser URLs. Local files are snapshotted
    when the app server starts and served through authenticated endpoints.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, strict=True, min_length=1)
    """Title used in the browser tab and app header."""

    favicon: AppImageIcon | str | Path | None = None
    """Browser tab image; a string means a URL, a Path means a local file."""

    icon: AppEmojiIcon | AppImageIcon | None = None
    """Header icon with exactly one of ``emoji``, ``url``, or ``path``."""

    @field_validator("favicon", mode="before")
    @classmethod
    def validate_favicon(cls, value: object) -> object:
        """Normalize local shorthand without losing it in saved JSON profiles."""
        if isinstance(value, Path):
            return AppImageIcon(path=value)
        if isinstance(value, str) and not value:
            raise ValueError("Favicon URL must not be empty.")
        return value

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
