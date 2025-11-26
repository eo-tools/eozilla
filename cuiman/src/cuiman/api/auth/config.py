#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Optional

from pydantic import BaseModel

from enum import Enum


class AuthType(str, Enum):
    """Authentication type."""

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

    def __repr__(self):
        return str(self)

    @classmethod
    def get_member(cls, name: str) -> Optional["AuthType"]:
        name_uc = name.upper()
        for m in AuthType:
            if m.value == name_uc:
                return m
        return None

    @classmethod
    def get_names(cls, lc: bool = False) -> tuple[str, ...]:
        return tuple((m.name.lower() if lc else m.name) for m in AuthType)


class AuthConfig(BaseModel):
    """Authentication configuration."""

    # Authentication type
    auth_type: AuthType | None = None

    # Authentication URL, usually an endpoint called "/auth/login".
    auth_url: Optional[str] = None

    # For BASIC or LOGIN (username/password -> token)
    username: Optional[str] = None
    password: Optional[str] = None

    # For TOKEN or LOGIN
    token: Optional[str] = None

    # For API_KEY
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"

    # For TOKEN (custom header) or Bearer
    token_header: str = "X-Auth-Token"
    use_bearer: bool = False  # if True → Authorization: Bearer <token>
