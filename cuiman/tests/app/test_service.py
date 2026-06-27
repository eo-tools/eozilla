#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pytest

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
            auth_type="login",
            auth_url="https://auth.example.test/login",
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
        "authType": "login",
        "authUrl": "https://auth.example.test/login",
        "grantType": "password",
        "useBearer": True,
    }


@pytest.mark.parametrize(
    ("config_kwargs", "expected_options"),
    [
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": None,
                "auth_url": "https://auth.example.test/auth",
                "username": "user",
                "password": "secret",
                "grant_type": "password",
                "token": "token-123",
                "refresh_token": "refresh-123",
                "use_bearer": False,
                "token_header": "X-Custom-Token",
                "api_key": "api-key-123",
                "api_key_header": "X-Custom-Api-Key",
            },
            {
                "apiUrl": "https://process.example.test/api",
            },
            id="auth-type-none-omits-auth-options",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "none",
                "auth_url": "https://auth.example.test/auth",
                "username": "user",
                "password": "secret",
                "grant_type": "password",
                "token": "token-123",
                "refresh_token": "refresh-123",
                "use_bearer": False,
                "token_header": "X-Custom-Token",
                "api_key": "api-key-123",
                "api_key_header": "X-Custom-Api-Key",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "none",
            },
            id="explicit-auth-type-none-keeps-auth-type",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "basic",
                "auth_url": "https://auth.example.test/auth",
                "username": "user",
                "password": "secret",
                "token": "token-123",
                "refresh_token": "refresh-123",
                "use_bearer": False,
                "token_header": "X-Custom-Token",
                "api_key": "api-key-123",
                "api_key_header": "X-Custom-Api-Key",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "basic",
                "authUrl": "https://auth.example.test/auth",
                "username": "user",
                "password": "secret",
            },
            id="basic-auth-keeps-basic-fields",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "login",
                "auth_url": "https://auth.example.test/auth",
                "username": "user",
                "password": "secret",
                "token": "token-123",
                "refresh_token": "refresh-123",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "grant_type": "client_credentials",
                "token_header": "X-Custom-Token",
                "api_key": "api-key-123",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "login",
                "authUrl": "https://auth.example.test/auth",
                "grantType": "client_credentials",
                "username": "user",
                "password": "secret",
                "token": "token-123",
                "refreshToken": "refresh-123",
                "clientId": "client-id",
                "clientSecret": "client-secret",
                "useBearer": True,
            },
            id="login-bearer-removes-token-header",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "login",
                "auth_url": "https://auth.example.test/auth",
                "token": "token-123",
                "use_bearer": False,
                "token_header": "X-Custom-Token",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "login",
                "authUrl": "https://auth.example.test/auth",
                "grantType": "password",
                "token": "token-123",
                "useBearer": False,
                "tokenHeader": "X-Custom-Token",
            },
            id="login-custom-header-keeps-token-header",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "token",
                "auth_url": "https://auth.example.test/auth",
                "token": "token-123",
                "refresh_token": "refresh-123",
                "token_header": "X-Custom-Token",
                "username": "user",
                "password": "secret",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "token",
                "authUrl": "https://auth.example.test/auth",
                "token": "token-123",
                "refreshToken": "refresh-123",
                "useBearer": True,
            },
            id="token-bearer-removes-token-header",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "token",
                "auth_url": "https://auth.example.test/auth",
                "token": "token-123",
                "use_bearer": False,
                "token_header": "X-Custom-Token",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "token",
                "authUrl": "https://auth.example.test/auth",
                "token": "token-123",
                "useBearer": False,
                "tokenHeader": "X-Custom-Token",
            },
            id="token-custom-header-keeps-token-header",
        ),
        pytest.param(
            {
                "api_url": "https://process.example.test/api",
                "auth_type": "api-key",
                "auth_url": "https://auth.example.test/auth",
                "api_key": "api-key-123",
                "username": "user",
                "password": "secret",
                "token": "token-123",
            },
            {
                "apiUrl": "https://process.example.test/api",
                "authType": "api-key",
                "authUrl": "https://auth.example.test/auth",
                "apiKey": "api-key-123",
                "apiKeyHeader": "X-API-Key",
            },
            id="api-key-auth-keeps-default-api-key-header",
        ),
    ],
)
def test_create_app_service_provider_keeps_only_applicable_options(
    config_kwargs, expected_options
):
    provider = create_app_service_provider(ClientConfig(**config_kwargs))

    assert provider.options == expected_options


def test_service_provider_models_accept_optional_metadata_and_options():
    provider = ServiceProvider(
        id="dev",
        meta=ServiceProviderMeta(
            type="dev",
            title="Development",
            disabled=False,
            hidden=True,
        ),
        options={
            "enabled": True,
            "retries": 2,
            "timeout": 3.5,
            "label": "local",
            "token": None,
        },
    )

    assert provider.model_dump() == {
        "id": "dev",
        "meta": {
            "type": "dev",
            "title": "Development",
            "description": None,
            "disabled": False,
            "hidden": True,
        },
        "options": {
            "enabled": True,
            "retries": 2,
            "timeout": 3.5,
            "label": "local",
            "token": None,
        },
    }
