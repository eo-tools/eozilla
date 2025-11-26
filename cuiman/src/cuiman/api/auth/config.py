#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Optional

from pydantic import BaseModel, Field

from .strategy import AuthStrategy


class AuthConfig(BaseModel):
    base_url: str = Field(..., description="Base URL of the API")

    # Auth settings
    auth_strategy: AuthStrategy = AuthStrategy.NONE

    # For LOGIN (username/password -> token)
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

    # For BASIC
    basic_username: Optional[str] = None
    basic_password: Optional[str] = None
