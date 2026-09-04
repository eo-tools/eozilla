#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

# ruff: noqa: S105, S106

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cuiman.api.auth import OidcAuthConfig, TokenResult
from cuiman.api.auth.oidc_async import renew_oidc_tokens_async


def make_auth(**kwargs: object) -> OidcAuthConfig:
    return OidcAuthConfig.model_validate(
        {
            "issuer_url": "https://identity.example.test",
            "client_id": "client",
            "refresh_token": "refresh",
            **kwargs,
        }
    )


@pytest.mark.asyncio
async def test_renew_oidc_tokens_async_discovers_and_refreshes():
    discovery_response = MagicMock()
    discovery_response.json.return_value = {
        "issuer": "https://identity.example.test/",
        "authorization_endpoint": "https://identity.example.test/authorize",
        "token_endpoint": "https://identity.example.test/token",
    }
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "access"}
    with (
        patch("httpx.AsyncClient.get", new=AsyncMock(return_value=discovery_response)),
        patch(
            "httpx.AsyncClient.post", new=AsyncMock(return_value=token_response)
        ) as post,
    ):
        result = await renew_oidc_tokens_async(make_auth())

    assert result == TokenResult(access_token="access")
    post.assert_awaited_once_with(
        "https://identity.example.test/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": "refresh",
            "client_id": "client",
        },
    )


@pytest.mark.asyncio
async def test_renew_oidc_tokens_async_requires_a_refresh_token():
    with pytest.raises(ValueError, match="refresh token"):
        await renew_oidc_tokens_async(make_auth(refresh_token=None))
