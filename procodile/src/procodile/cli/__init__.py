#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# No exports here. To avoid unnecessary imports, CLI apps should pick
# only what they need from dedicated submodules.

from .cli import get_cli

__all__ = ["get_cli"]
