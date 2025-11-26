#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Literal, Optional, TypeAlias, get_args

from pydantic import BaseModel

AuthType: TypeAlias = Literal[
    # No authentication required
    "none",
    # HTTP Basic Auth.
    "basic",
    # Static token (X-Auth-Token or Bearer)
    "token",
    # username/password (X-Auth-Token or Bearer)
    "login",
    # X-API-Key.
    "api-key",
]

AUTH_TYPE_NAMES: tuple[str, ...] = get_args(AuthType)


class AuthConfig(BaseModel):
    """Authentication configuration."""

    # Authentication type
    auth_type: Optional[AuthType] = None

    # Authentication URL, usually an endpoint called "/auth/login".
    auth_url: Optional[str] = None

    # For BASIC or LOGIN (username/password -> token)
    username: Optional[str] = None
    password: Optional[str] = None

    # For TOKEN or LOGIN
    token: Optional[str] = None

    # For TOKEN: custom header or Bearer
    use_bearer: bool = False  # if True → Authorization: Bearer <token>
    token_header: str = "X-Auth-Token"

    # For API_KEY
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
