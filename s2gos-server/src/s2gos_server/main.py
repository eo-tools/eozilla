#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from . import routes
from .app import app
from .provider import ServiceProvider

"""
This module imports both, the FastAPI `app` instance and the application's 
path functions. It also sets the server's service instance and exports the 
the application as the `app` module attribute.
"""

ServiceProvider.init()
print(f"Running service {ServiceProvider.instance()}")

__all__ = ["app", "routes"]
