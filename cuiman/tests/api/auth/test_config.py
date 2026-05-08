#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cuiman.api.auth import AuthConfig
from cuiman.api.auth.login import LoginResult


def test_auth_headers_none():
    config = AuthConfig(auth_type=None)
    assert config.auth_headers == {}
    config = AuthConfig(auth_type="none")
    assert config.auth_headers == {}


def test_auth_headers_token_custom_header():
    config = AuthConfig(
        auth_type="token",
        token="abc123",
        token_header="X-Auth-Token",
        use_bearer=False,
    )
    assert config.auth_headers == {"X-Auth-Token": "abc123"}


def test_auth_headers_token_bearer():
    config = AuthConfig(
        auth_type="token",
        token="abc123",
        use_bearer=True,
    )
    assert config.auth_headers == {"Authorization": "Bearer abc123"}


def test_auth_headers_login_bearer():
    config = AuthConfig(auth_type="login", token="xyz")
    assert config.auth_headers == {"Authorization": "Bearer xyz"}


def test_auth_headers_login_custom_header():
    config = AuthConfig(
        auth_type="login",
        token="xyz",
        use_bearer=False,
        token_header="X-Token",
    )
    assert config.auth_headers == {"X-Token": "xyz"}


def test_auth_headers_api_key():
    config = AuthConfig(
        auth_type="api-key",
        api_key="mykey",
        api_key_header="X-API-Key",
    )
    assert config.auth_headers == {"X-API-Key": "mykey"}


def test_auth_headers_basic_auth():
    config = AuthConfig(
        auth_type="basic",
        username="user",
        password="pass",
    )
    headers = config.auth_headers
    assert "Authorization" in headers

    expected = base64.b64encode(b"user:pass").decode()
    assert headers["Authorization"] == f"Basic {expected}"


def test_auth_headers_fail():
    assert_auth_headers_fail(
        AuthConfig(auth_type="token", token=""), "Missing API token."
    )
    assert_auth_headers_fail(
        AuthConfig(auth_type="login", token=""),
        "Token is missing. Run CLI 'configure' first.",
    )
    assert_auth_headers_fail(
        AuthConfig(auth_type="api-key", api_key=""),
        "api_key must be set for authentication type 'api-key'.",
    )
    assert_auth_headers_fail(
        AuthConfig(auth_type="basic", username="jo", password=""),
        "username/password required for basic authentication.",
    )
    assert_auth_headers_fail(
        AuthConfig(auth_type="basic", username="", password="123"),
        "username/password required for basic authentication.",
    )


def test_make_token_refresher_returns_none_when_not_login():
    config = AuthConfig(auth_type="token", token="abc")
    assert config._maybe_make_token_refresher() is None


def test_make_token_refresher_returns_none_when_no_refresh_token():
    config = AuthConfig(auth_type="login", token="abc")
    assert config._maybe_make_token_refresher() is None


@patch("cuiman.api.auth.login.refresh_login")
def test_make_token_refresher_calls_refresh_login(mock_refresh: MagicMock):
    mock_refresh.return_value = LoginResult(
        access_token="new-token", refresh_token="new-refresh"
    )
    config = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/token",
        token="old-token",
        refresh_token="old-refresh",
        use_bearer=False,
        token_header="X-Auth-Token",
    )
    refresher = config._maybe_make_token_refresher()
    assert refresher is not None
    headers = refresher()
    mock_refresh.assert_called_once_with(config)
    assert config.token == "new-token"
    assert config.refresh_token == "new-refresh"
    assert headers == {"X-Auth-Token": "new-token"}


@patch("cuiman.api.auth.login.refresh_login")
def test_make_token_refresher_without_new_refresh_token(mock_refresh: MagicMock):
    mock_refresh.return_value = LoginResult(
        access_token="new-token", refresh_token=None
    )
    config = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/token",
        token="old-token",
        refresh_token="old-refresh",
    )
    refresher = config._maybe_make_token_refresher()
    refresher()
    assert config.token == "new-token"
    assert config.refresh_token == "old-refresh"


def test_make_async_token_refresher_returns_none_when_not_login():
    config = AuthConfig(auth_type="token", token="abc")
    assert config._make_async_token_refresher() is None


def test_make_async_token_refresher_returns_none_when_no_refresh_token():
    config = AuthConfig(auth_type="login", token="abc")
    assert config._make_async_token_refresher() is None


@pytest.mark.asyncio
@patch("cuiman.api.auth.login_async.refresh_login_async")
async def test_make_async_token_refresher_calls_refresh(mock_refresh: MagicMock):
    mock_refresh.return_value = LoginResult(
        access_token="new-token", refresh_token="new-refresh"
    )
    config = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/token",
        token="old-token",
        refresh_token="old-refresh",
        use_bearer=False,
        token_header="X-Auth-Token",
    )
    refresher = config._make_async_token_refresher()
    assert refresher is not None
    headers = await refresher()
    mock_refresh.assert_called_once_with(config)
    assert config.token == "new-token"
    assert config.refresh_token == "new-refresh"
    assert headers == {"X-Auth-Token": "new-token"}


@pytest.mark.asyncio
@patch("cuiman.api.auth.login_async.refresh_login_async")
async def test_make_async_token_refresher_without_new_refresh_token(
    mock_refresh: MagicMock,
):
    mock_refresh.return_value = LoginResult(
        access_token="new-token", refresh_token=None
    )
    config = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/token",
        token="old-token",
        refresh_token="old-refresh",
    )
    refresher = config._make_async_token_refresher()
    await refresher()
    assert config.token == "new-token"
    assert config.refresh_token == "old-refresh"


def assert_auth_headers_fail(config: AuthConfig, match: str):
    with pytest.raises(ValueError, match=match):
        _headers = config.auth_headers
