#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

from unittest.mock import MagicMock, patch

import pytest

from cuiman.api.auth import OAuth2AuthConfig, TokenResult
from cuiman.api.auth.oauth2 import (
    obtain_oauth2_tokens,
    prepare_oauth2_renewal_request,
    prepare_oauth2_token_request,
    process_oauth2_token_response,
    renew_oauth2_tokens,
)


def password_config(**kwargs) -> OAuth2AuthConfig:
    return OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        username="u",
        password="p",
        client_id="client",
        client_secret="secret",
        **kwargs,
    )


def client_config(**kwargs) -> OAuth2AuthConfig:
    return OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        grant_type="client_credentials",
        client_id="client",
        client_secret="secret",
        **kwargs,
    )


def test_prepare_password_grant():
    url, data = prepare_oauth2_token_request(password_config())
    assert url == "https://identity.example.test/token"
    assert data == {
        "grant_type": "password",
        "username": "u",
        "password": "p",
        "client_id": "client",
        "client_secret": "secret",
    }


def test_prepare_password_grant_without_client_credentials():
    config = OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        username="u",
        password="p",
    )
    _, data = prepare_oauth2_token_request(config)
    assert data == {"grant_type": "password", "username": "u", "password": "p"}


def test_prepare_client_credentials_grant():
    _, data = prepare_oauth2_token_request(client_config())
    assert data == {
        "grant_type": "client_credentials",
        "client_id": "client",
        "client_secret": "secret",
    }


def test_password_grant_renewal_uses_refresh_token():
    _, data = prepare_oauth2_renewal_request(password_config(refresh_token="refresh"))
    assert data == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh",
        "client_id": "client",
        "client_secret": "secret",
    }


def test_password_grant_without_refresh_token_is_reacquired():
    assert prepare_oauth2_renewal_request(password_config()) == (
        "https://identity.example.test/token",
        {
            "grant_type": "password",
            "username": "u",
            "password": "p",
            "client_id": "client",
            "client_secret": "secret",
        },
    )


def test_client_credentials_grant_is_reacquired_on_renewal():
    assert prepare_oauth2_renewal_request(client_config())[1]["grant_type"] == (
        "client_credentials"
    )


def test_obtain_oauth2_tokens():
    response = MagicMock()
    response.json.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
    }
    with patch("httpx.Client.post", return_value=response) as post:
        result = obtain_oauth2_tokens(password_config())

    assert result == TokenResult(access_token="access", refresh_token="refresh")
    post.assert_called_once()


def test_renew_oauth2_tokens():
    response = MagicMock()
    response.json.return_value = {"access_token": "renewed"}
    with patch("httpx.Client.post", return_value=response):
        result = renew_oauth2_tokens(client_config())
    assert result == TokenResult(access_token="renewed")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (["not", "an", "object"], "JSON object"),
        ({}, "access_token"),
        ({"access_token": ""}, "access_token"),
        ({"access_token": "a", "refresh_token": 42}, "refresh_token"),
    ],
)
def test_process_oauth2_token_response_rejects_invalid_payload(payload, message):
    response = MagicMock()
    response.json.return_value = payload
    with pytest.raises(RuntimeError, match=message):
        process_oauth2_token_response(response)
