#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Export the FastAPI application with its Core routes registered.

DRU routes are registered separately when a DRU-capable service is loaded.
"""

from .app import app
from .routes import core

__all__ = ["app", "core"]
