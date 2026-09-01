#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import httpx

from .config import OAuth2AuthConfig
from .login import TokenResult
from .oauth2 import (
    prepare_oauth2_renewal_request,
    prepare_oauth2_token_request,
    process_oauth2_token_response,
)


async def obtain_oauth2_tokens_async(
    auth_config: OAuth2AuthConfig,
) -> TokenResult:
    """Asynchronously obtain OAuth2 tokens using the configured grant."""
    url, data = prepare_oauth2_token_request(auth_config)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        return process_oauth2_token_response(response)


async def renew_oauth2_tokens_async(
    auth_config: OAuth2AuthConfig,
) -> TokenResult:
    """Asynchronously refresh or reacquire OAuth2 tokens."""
    url, data = prepare_oauth2_renewal_request(auth_config)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, data=data)
        return process_oauth2_token_response(response)
