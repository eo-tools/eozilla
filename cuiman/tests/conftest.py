#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path

import pytest

from cuiman.api.config import ClientConfig


@pytest.fixture(autouse=True)
def isolate_default_client_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prevent tests from loading a developer's real client configuration."""
    monkeypatch.setattr(ClientConfig, "default_path", tmp_path / "config")
