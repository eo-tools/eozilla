#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .api.async_client import AsyncClient
from .api.client import Client
from .api.config import ClientConfig
from .api.exceptions import ClientError


def _read_version() -> str:
    try:
        package_version = version("cuiman")
    except PackageNotFoundError:
        package_version = None

    if package_version:
        return package_version

    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject_path.exists():
        for line in pyproject_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')

    return "0.1.2.dev0"


__version__ = _read_version()

__all__ = [
    "AsyncClient",
    "Client",
    "ClientConfig",
    "ClientError",
    "__version__",
]
