#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from enum import Enum


class AuthStrategy(str, Enum):
    NONE = "none"
    """No authentication required."""

    TOKEN = "token"
    """Static token: X-Auth-Token or Bearer."""

    LOGIN = "login"
    """username/password -> token."""

    BASIC = "basic"
    """# HTTP Basic Auth."""

    API_KEY = "api_key"
    """X-API-Key."""
