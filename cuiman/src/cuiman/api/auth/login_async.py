#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import httpx

from .config import AuthConfig
from .login import prepare_login, process_login_response


async def login_async(auth_config: AuthConfig) -> Any:
    """
    Performs an asynchronous login (username+password → token)
    and returns a token.

    Args:
        auth_config: authentication configuration.

    Returns:
        An access token either as JSON or plain text.
    """
    data = prepare_login(auth_config)
    async with httpx.AsyncClient() as client:
        assert auth_config.auth_url is not None
        response = await client.post(auth_config.auth_url, data=data)
        return process_login_response(response)
