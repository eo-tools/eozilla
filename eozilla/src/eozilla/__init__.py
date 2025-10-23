#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from importlib.metadata import version

import appligator
import cuiman
import gavicore
import procodile
import wraptile

__version__ = version("eozilla")

__all__ = [
    "__version__",
    "appligator",
    "cuiman",
    "gavicore",
    "procodile",
    "wraptile",
]
