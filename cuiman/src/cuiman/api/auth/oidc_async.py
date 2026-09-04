#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0 License.

"""Asynchronous OpenID Connect token-renewal helpers."""

import httpx

from .config import OidcAuthConfig
from .login import TokenResult
from .oauth2 import process_oauth2_token_response
from .oidc import (
    parse_oidc_discovery,
    prepare_oidc_discovery,
    prepare_oidc_refresh_request,
)


async def renew_oidc_tokens_async(auth_config: OidcAuthConfig) -> TokenResult:
    """Refresh an OIDC access token using its stored refresh token."""
    data = prepare_oidc_refresh_request(auth_config)
    issuer_url, metadata_url = prepare_oidc_discovery(auth_config)
    async with httpx.AsyncClient() as client:
        discovery_response = await client.get(metadata_url)
        discovery = parse_oidc_discovery(discovery_response, issuer_url)
        response = await client.post(discovery.token_endpoint, data=data)
    return process_oauth2_token_response(response)
