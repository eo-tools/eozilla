#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cuiman.api.auth import OAuth2AuthConfig, TokenResult
from cuiman.api.auth.oauth2_async import (
    obtain_oauth2_tokens_async,
    renew_oauth2_tokens_async,
)


def make_config(**kwargs) -> OAuth2AuthConfig:
    return OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        grant_type="client_credentials",
        client_id="client",
        client_secret="secret",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_obtain_oauth2_tokens_async():
    response = MagicMock()
    response.json.return_value = {"access_token": "access"}
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        result = await obtain_oauth2_tokens_async(make_config())
    assert result == TokenResult(access_token="access")


@pytest.mark.asyncio
async def test_renew_oauth2_tokens_async():
    response = MagicMock()
    response.json.return_value = {"access_token": "renewed"}
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        result = await renew_oauth2_tokens_async(make_config())
    assert result == TokenResult(access_token="renewed")
