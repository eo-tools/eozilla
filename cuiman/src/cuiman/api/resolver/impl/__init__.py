#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Built-in job result resolver implementations."""

from .stac import StacResolver
from .value import ValueResolver

__all__ = ["StacResolver", "ValueResolver"]
