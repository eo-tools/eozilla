#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import base64

import pytest
from pydantic import TypeAdapter, ValidationError

from cuiman.api.auth import (
    ApiKeyAuthConfig,
    AuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OidcAuthConfig,
    TokenAuthConfig,
)


def test_auth_config_rejects_fields_from_another_auth_type():
    with pytest.raises(ValidationError, match="token_url"):
        TypeAdapter(AuthConfig).validate_python(
            {"auth_type": "none", "token_url": "https://example.test/token"}
        )


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


def test_oidc_requires_a_client_id():
    with pytest.raises(ValidationError, match="at least 1 character"):
        OidcAuthConfig(
            issuer_url="https://identity.example.test",
            client_id="",
        )
