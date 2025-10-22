#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# Important: this module shall have no dependencies other
# than the Python std lib.

from pathlib import Path
from typing import Final

DEFAULT_USER_PATH: Final = Path("~").expanduser() / ".eozilla"
DEFAULT_CONFIG_PATH: Final = DEFAULT_USER_PATH / "config"

DEFAULT_SERVER_URL: Final = "http://127.0.0.1:8008"
