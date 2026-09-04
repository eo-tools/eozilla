#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import TypeAdapter, ValidationError

from cuiman.api.auth import (
    ApiKeyAuthConfig,
    AuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
    TokenResult,
)


@pytest.mark.parametrize(
    ("data", "expected_type"),
    [
        ({"auth_type": "none"}, NoAuthConfig),
        (
            {"auth_type": "basic", "username": "u", "password": "p"},
            BasicAuthConfig,
        ),
        ({"auth_type": "token", "access_token": "t"}, TokenAuthConfig),
        (
            {
                "auth_type": "login",
                "login_url": "https://example.test/login",
                "username": "u",
                "password": "p",
            },
            LoginAuthConfig,
        ),
        (
            {
                "auth_type": "oauth2",
                "token_url": "https://example.test/token",
                "username": "u",
                "password": "p",
            },
            OAuth2AuthConfig,
        ),
        ({"auth_type": "api-key", "api_key": "k"}, ApiKeyAuthConfig),
    ],
)
def test_auth_config_discriminator(data, expected_type):
    config = TypeAdapter(AuthConfig).validate_python(data)
    assert isinstance(config, expected_type)


def test_auth_config_rejects_fields_from_another_auth_type():
    with pytest.raises(ValidationError, match="token_url"):
        TypeAdapter(AuthConfig).validate_python(
            {"auth_type": "none", "token_url": "https://example.test/token"}
        )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (NoAuthConfig(), {"auth_type": "none"}),
        (BasicAuthConfig(username="u", password="p"), {"auth_type": "basic"}),
        (
            TokenAuthConfig(access_token="token"),
            {
                "auth_type": "token",
                "use_bearer": True,
                "access_token_header": "X-Auth-Token",
            },
        ),
        (
            LoginAuthConfig(
                login_url="https://example.test/login",
                username="u",
                password="p",
                access_token="token",
            ),
            {
                "auth_type": "login",
                "login_url": "https://example.test/login",
                "use_bearer": True,
                "access_token_header": "X-Auth-Token",
            },
        ),
        (
            OAuth2AuthConfig(
                token_url="https://example.test/token",
                username="u",
                password="p",
                client_id="client",
                client_secret="secret",
                access_token="token",
                refresh_token="refresh",
            ),
            {
                "auth_type": "oauth2",
                "token_url": "https://example.test/token",
                "grant_type": "password",
                "client_id": "client",
                "use_bearer": True,
                "access_token_header": "X-Auth-Token",
            },
        ),
        (
            ApiKeyAuthConfig(api_key="key"),
            {"auth_type": "api-key", "api_key_header": "X-API-Key"},
        ),
    ],
)
def test_public_auth_config_excludes_secrets(config, expected):
    assert config.to_public_dict() == expected


def test_no_auth_headers():
    assert NoAuthConfig().auth_headers == {}


def test_basic_auth_headers():
    config = BasicAuthConfig(username="user", password="pass")
    expected = base64.b64encode(b"user:pass").decode()
    assert config.auth_headers == {"Authorization": f"Basic {expected}"}


@pytest.mark.parametrize(("username", "password"), [("", "p"), ("u", "")])
def test_basic_auth_headers_require_non_empty_credentials(username, password):
    config = BasicAuthConfig(username=username, password=password)
    with pytest.raises(ValueError, match="username/password required"):
        _ = config.auth_headers


def test_access_token_headers():
    assert TokenAuthConfig(access_token="abc").auth_headers == {
        "Authorization": "Bearer abc"
    }
    assert TokenAuthConfig(
        access_token="abc",
        use_bearer=False,
        access_token_header="X-Token",
    ).auth_headers == {"X-Token": "abc"}


def test_login_requires_access_token_for_headers():
    config = LoginAuthConfig(
        login_url="https://example.test/login",
        username="u",
        password="p",
    )
    with pytest.raises(ValueError, match="Missing access token"):
        _ = config.auth_headers


def test_api_key_headers():
    assert ApiKeyAuthConfig(api_key="key").auth_headers == {"X-API-Key": "key"}
    assert ApiKeyAuthConfig(
        api_key="key", api_key_header="X-Custom-Key"
    ).auth_headers == {"X-Custom-Key": "key"}


def test_api_key_requires_non_empty_value():
    with pytest.raises(ValueError, match="api_key must be set"):
        _ = ApiKeyAuthConfig(api_key="").auth_headers


def test_oauth2_password_grant_allows_credentials_to_be_resolved_later():
    config = OAuth2AuthConfig(token_url="https://example.test/token")
    assert config.username is None
    assert config.password is None


@pytest.mark.parametrize(("username", "password"), [("u", None), (None, "p")])
def test_oauth2_password_grant_rejects_incomplete_credentials(username, password):
    with pytest.raises(ValidationError, match="Username and password"):
        OAuth2AuthConfig(
            token_url="https://example.test/token",
            username=username,
            password=password,
        )


def test_oauth2_client_credentials_grant_requires_client_id():
    with pytest.raises(ValidationError, match="Client ID is required"):
        OAuth2AuthConfig(
            token_url="https://example.test/token",
            grant_type="client_credentials",
        )


def test_non_oauth_configs_have_no_refreshers():
    config = NoAuthConfig()
    assert config.make_token_refresher() is None
    assert config.make_async_token_refresher() is None


@patch("cuiman.api.auth.oauth2.renew_oauth2_tokens")
def test_oauth2_refresher_updates_tokens(mock_renew: MagicMock):
    mock_renew.return_value = TokenResult(
        access_token="new-access", refresh_token="new-refresh"
    )
    config = OAuth2AuthConfig(
        token_url="https://example.test/token",
        username="u",
        password="p",
        access_token="old-access",
        refresh_token="old-refresh",
        use_bearer=False,
        access_token_header="X-Token",
    )
    refresher = config.make_token_refresher()

    assert refresher() == {"X-Token": "new-access"}
    mock_renew.assert_called_once_with(config)
    assert config.access_token == "new-access"
    assert config.refresh_token == "new-refresh"


@patch("cuiman.api.auth.oauth2.renew_oauth2_tokens")
def test_oauth2_refresher_preserves_unrotated_refresh_token(mock_renew: MagicMock):
    mock_renew.return_value = TokenResult(access_token="new-access")
    config = OAuth2AuthConfig(
        token_url="https://example.test/token",
        username="u",
        password="p",
        refresh_token="old-refresh",
    )

    config.make_token_refresher()()

    assert config.refresh_token == "old-refresh"


@pytest.mark.asyncio
@patch(
    "cuiman.api.auth.oauth2_async.renew_oauth2_tokens_async",
    new_callable=AsyncMock,
)
async def test_oauth2_async_refresher_updates_tokens(mock_renew: AsyncMock):
    mock_renew.return_value = TokenResult(
        access_token="new-access", refresh_token="new-refresh"
    )
    config = OAuth2AuthConfig(
        token_url="https://example.test/token",
        username="u",
        password="p",
        access_token="old-access",
        refresh_token="old-refresh",
    )

    headers = await config.make_async_token_refresher()()

    assert headers == {"Authorization": "Bearer new-access"}
    assert config.refresh_token == "new-refresh"


@pytest.mark.asyncio
@patch(
    "cuiman.api.auth.oauth2_async.renew_oauth2_tokens_async",
    new_callable=AsyncMock,
)
async def test_client_credentials_refresher_ignores_refresh_token(
    mock_renew: AsyncMock,
):
    mock_renew.return_value = TokenResult(
        access_token="new-access", refresh_token="unused-refresh"
    )
    config = OAuth2AuthConfig(
        token_url="https://example.test/token",
        grant_type="client_credentials",
        client_id="client",
        client_secret="secret",
        access_token="old-access",
    )

    await config.make_async_token_refresher()()

    assert config.access_token == "new-access"
    assert config.refresh_token is None
