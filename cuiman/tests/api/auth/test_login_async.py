#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cuiman.api.auth import LoginAuthConfig, TokenResult, login_async


def make_config() -> LoginAuthConfig:
    return LoginAuthConfig(
        login_url="https://example.test/login",
        username="u",
        password="p",
    )


@pytest.mark.asyncio
async def test_login_async_json():
    response = MagicMock()
    response.json.return_value = {"token": "abc123"}

    with patch("httpx2.AsyncClient.post", new=AsyncMock(return_value=response)):
        assert await login_async(make_config()) == TokenResult(access_token="abc123")


@pytest.mark.asyncio
async def test_login_async_plaintext():
    response = MagicMock()
    response.json.side_effect = json.JSONDecodeError("not json", "", 0)
    response.text = "plaintext-token"

    with patch("httpx2.AsyncClient.post", new=AsyncMock(return_value=response)):
        assert await login_async(make_config()) == TokenResult(
            access_token="plaintext-token"
        )


@pytest.mark.asyncio
async def test_login_async():
    response = MagicMock()
    response.json.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
    }

    with patch("httpx2.AsyncClient.post", new=AsyncMock(return_value=response)):
        result = await login_async(make_config())

    assert result == TokenResult(access_token="access", refresh_token="refresh")
