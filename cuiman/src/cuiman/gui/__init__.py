#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import panel as pn

from .client import Client

__all__ = ["Client"]

pn.extension("ipywidgets", "tabulator", notifications=True)
