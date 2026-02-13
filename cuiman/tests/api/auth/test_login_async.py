from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cuiman.api.auth import AuthConfig, login_async


@pytest.mark.asyncio
async def test_login_async_json():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        client_id="my-client",
        client_secret="my-secret",
        username="u",
        password="p",
    )

    # mock AsyncClient.post
    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status.return_value = None

    # noinspection PyUnusedLocal
    async def fake_post(url, data):
        return mock_response

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=fake_post)):
        token = await login_async(cfg)

    assert token == "abc123"


@pytest.mark.asyncio
async def test_login_async_plaintext():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        client_id="my-client",
        client_secret="my-secret",
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("not json")
    mock_response.text = "plaintext-token"
    mock_response.raise_for_status.return_value = None

    # noinspection PyUnusedLocal
    async def fake_post(url, data):
        return mock_response

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=fake_post)):
        token = await login_async(cfg)

    assert token == "plaintext-token"


@pytest.mark.asyncio
async def test_login_async_missing_credentials():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        username=None,
        password=None,
    )

    with pytest.raises(ValueError):
        await login_async(cfg)
