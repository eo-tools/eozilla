#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S106

import pytest

from cuiman.api.auth import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
)
from cuiman.api.config import ClientConfig
from cuiman.app.service import (
    ServiceProvider,
    ServiceProviderMeta,
    create_app_service_provider,
)


def test_create_app_service_provider():
    provider = create_app_service_provider(
        ClientConfig(
            api_url="https://process.example.test/api",
            auth=LoginAuthConfig(
                login_url="https://auth.example.test/login",
                username="user",
                password="secret",
                access_token="resolved-token",
            ),
        )
    )

    assert isinstance(provider, ServiceProvider)
    assert provider.id == "client"
    assert provider.meta == ServiceProviderMeta(
        type="custom",
        title="Client",
        description="In-app provider",
    )
    assert provider.options == {
        "apiUrl": "https://process.example.test/api",
        "authType": "token",
        "accessToken": "resolved-token",
        "useBearer": True,
    }


@pytest.mark.parametrize(
    ("auth", "expected_auth_options"),
    [
        pytest.param(NoAuthConfig(), {"authType": "none"}, id="none"),
        pytest.param(
            BasicAuthConfig(username="user", password="secret"),
            {"authType": "basic", "username": "user", "password": "secret"},
            id="basic",
        ),
        pytest.param(
            TokenAuthConfig(access_token="token"),
            {"authType": "token", "accessToken": "token", "useBearer": True},
            id="bearer-token",
        ),
        pytest.param(
            TokenAuthConfig(
                access_token="token",
                use_bearer=False,
                access_token_header="X-Custom-Token",
            ),
            {
                "authType": "token",
                "accessToken": "token",
                "useBearer": False,
                "accessTokenHeader": "X-Custom-Token",
            },
            id="custom-header-token",
        ),
        pytest.param(
            LoginAuthConfig(
                login_url="https://auth.example.test/login",
                username="user",
                password="secret",
            ),
            {
                "authType": "login",
                "loginUrl": "https://auth.example.test/login",
                "username": "user",
                "password": "secret",
                "useBearer": True,
            },
            id="unresolved-login",
        ),
        pytest.param(
            OAuth2AuthConfig(
                token_url="https://auth.example.test/token",
                username="user",
                password="secret",
                client_id="client",
            ),
            {
                "authType": "oauth2",
                "tokenUrl": "https://auth.example.test/token",
                "grantType": "password",
                "username": "user",
                "password": "secret",
                "clientId": "client",
                "useBearer": True,
            },
            id="unresolved-oauth2",
        ),
        pytest.param(
            ApiKeyAuthConfig(api_key="key", api_key_header="X-Key"),
            {"authType": "api-key", "apiKey": "key", "apiKeyHeader": "X-Key"},
            id="api-key",
        ),
    ],
)
def test_service_options_for_auth_models(auth, expected_auth_options):
    provider = create_app_service_provider(
        ClientConfig(api_url="https://process.example.test/api", auth=auth)
    )
    assert provider.options == {
        "apiUrl": "https://process.example.test/api",
        **expected_auth_options,
    }


def test_resolved_oauth2_is_forwarded_as_token_without_credentials():
    provider = create_app_service_provider(
        ClientConfig(
            api_url="https://process.example.test/api",
            auth=OAuth2AuthConfig(
                token_url="https://auth.example.test/token",
                grant_type="client_credentials",
                client_id="client",
                client_secret="secret",
                access_token="resolved-token",
                refresh_token="refresh",
            ),
        )
    )
    assert provider.options == {
        "apiUrl": "https://process.example.test/api",
        "authType": "token",
        "accessToken": "resolved-token",
        "useBearer": True,
    }
