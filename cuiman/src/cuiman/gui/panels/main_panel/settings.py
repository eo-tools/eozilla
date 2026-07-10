#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pydantic import BaseModel


class MainPanelSettings(BaseModel):
    """Used to persist main panel settings."""

    process_id: str | None = None
    """Last selected process identifier."""

    show_advanced: bool = False
    """Whether to show advanced input options."""

    last_dir: str | None = None
    """Last visited directory for file choosers."""

    last_path: str | None = None
    """Last visited file path for file choosers."""
