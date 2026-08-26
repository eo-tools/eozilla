#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import httpx

from .config import LoginAuthConfig
from .login import TokenResult, prepare_login, process_login_response_for_tokens


async def login_async(auth_config: LoginAuthConfig) -> str:
    """Asynchronously log in and return a proprietary access token."""
    return (await login_async_for_tokens(auth_config)).access_token


async def login_async_for_tokens(auth_config: LoginAuthConfig) -> TokenResult:
    """Asynchronously log in and parse the token response."""
    url, data = prepare_login(auth_config)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        return process_login_response_for_tokens(response)
