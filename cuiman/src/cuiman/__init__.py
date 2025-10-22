#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import version

from .api.async_client import AsyncClient
from .api.client import Client
from .api.config import ClientConfig
from .api.exceptions import ClientError

__version__ = version("cuiman")

__all__ = [
    "AsyncClient",
    "Client",
    "ClientConfig",
    "ClientError",
    "__version__",
]
