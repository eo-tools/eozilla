#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import version
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api.async_client import AsyncClient as AsyncClient
    from .api.client import Client as Client
    from .api.config import ClientConfig as ClientConfig
    from .api.exceptions import ClientError as ClientError
    from .api.jobs import JobMonitor as JobMonitor
    from .api.jobs import JobOptions as JobOptions

__version__ = version("cuiman")

__all__ = [
    "AsyncClient",
    "Client",
    "ClientConfig",
    "ClientError",
    "JobMonitor",
    "JobOptions",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Load public API exports only when requested, keeping CLI startup light."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(".api", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy public API exports in interactive discovery."""
    return sorted(set(globals()) | set(__all__))
