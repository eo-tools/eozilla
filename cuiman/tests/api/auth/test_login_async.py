from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from yourpkg.auth_login_async import login_and_get_token_async
from yourpkg.config import AuthStrategy, ClientConfig


@pytest.mark.asyncio
async def test_login_and_get_token_async_json():
    cfg = ClientConfig(
        base_url="http://api",
        auth_strategy=AuthStrategy.LOGIN,
        username="u",
        password="p",
    )

    # mock AsyncClient.post
    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status.return_value = None

    async def fake_post(url, data):
        return mock_response

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=fake_post)):
        token = await login_and_get_token_async(cfg)

    assert token == "abc123"
    assert cfg.token == "abc123"


@pytest.mark.asyncio
async def test_login_and_get_token_async_plaintext():
    cfg = ClientConfig(
        base_url="http://api",
        auth_strategy=AuthStrategy.LOGIN,
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("not json")
    mock_response.text = "plaintext-token"
    mock_response.raise_for_status.return_value = None

    async def fake_post(url, data):
        return mock_response

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=fake_post)):
        token = await login_and_get_token_async(cfg)

    assert token == "plaintext-token"
    assert cfg.token == "plaintext-token"


@pytest.mark.asyncio
async def test_login_and_get_token_async_missing_credentials():
    cfg = ClientConfig(
        base_url="http://api",
        auth_strategy=AuthStrategy.LOGIN,
        username=None,
        password=None,
    )

    with pytest.raises(ValueError):
        await login_and_get_token_async(cfg)
