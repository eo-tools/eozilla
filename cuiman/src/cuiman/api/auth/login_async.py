#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import httpx

from .config import AuthConfig
from .login import (
    LoginResult,
    prepare_login,
    prepare_refresh,
    process_login_response_for_tokens,
)


async def login_async(auth_config: AuthConfig) -> Any:
    """
    Performs an asynchronous login (username+password → token)
    and returns a token.

    Args:
        auth_config: authentication configuration.

    Returns:
        An access token either as JSON or plain text.
    """
    return (await login_async_for_tokens(auth_config)).access_token


async def login_async_for_tokens(auth_config: AuthConfig) -> LoginResult:
    """
    Performs an asynchronous login and returns both
    access token and refresh token (if available).

    Args:
        auth_config: authentication configuration.

    Returns:
        A LoginResult with access_token and optional refresh_token.
    """
    url, data = prepare_login(auth_config)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        return process_login_response_for_tokens(response)


async def refresh_login_async(auth_config: AuthConfig) -> LoginResult:
    """
    Performs an asynchronous token refresh using a refresh token.

    Args:
        auth_config: authentication configuration (must have refresh_token set).

    Returns:
        A LoginResult with the new access_token and optional new refresh_token.
    """
    url, data = prepare_refresh(auth_config)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        return process_login_response_for_tokens(response)
