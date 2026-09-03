#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import json
from unittest.mock import MagicMock, patch

import pytest

from cuiman.api.auth import LoginAuthConfig, TokenResult, login
from cuiman.api.auth.login import (
    login_for_tokens,
    parse_token,
    prepare_login,
    process_login_response,
)


def make_config(**kwargs) -> LoginAuthConfig:
    return LoginAuthConfig(
        login_url="https://example.test/login",
        username="u",
        password="p",
        **kwargs,
    )


def test_prepare_login_uses_proprietary_payload():
    url, data = prepare_login(make_config())
    assert url == "https://example.test/login"
    assert data == {"username": "u", "password": "p"}


@pytest.mark.parametrize(("username", "password"), [("", "p"), ("u", "")])
def test_prepare_login_requires_credentials(username, password):
    with pytest.raises(ValueError, match="Username and password"):
        prepare_login(
            LoginAuthConfig(
                login_url="https://example.test/login",
                username=username,
                password=password,
            )
        )


def test_login_json_response():
    response = MagicMock()
    response.json.return_value = {"token": "abc123"}

    with patch("httpx.Client.post", return_value=response) as post:
        token = login(make_config())

    assert token == "abc123"
    post.assert_called_once_with(
        "https://example.test/login",
        data={"username": "u", "password": "p"},
    )


def test_login_plaintext_response():
    response = MagicMock()
    response.json.side_effect = json.JSONDecodeError("not json", "", 0)
    response.text = "plaintext-token"

    with patch("httpx.Client.post", return_value=response):
        assert login(make_config()) == "plaintext-token"


def test_login_for_tokens_parses_optional_refresh_token():
    response = MagicMock()
    response.json.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
    }
    with patch("httpx.Client.post", return_value=response):
        result = login_for_tokens(make_config())

    assert result == TokenResult(access_token="access", refresh_token="refresh")


def test_process_login_response():
    response = MagicMock()
    response.json.return_value = {"authToken": "abc"}
    assert process_login_response(response) == "abc"


def test_process_login_response_plaintext():
    response = MagicMock()
    response.json.side_effect = ValueError("not json")
    response.text = "  abc  "
    assert process_login_response(response) == "abc"


def test_parse_token_common_shapes():
    assert parse_token("a1b2") == "a1b2"
    assert parse_token({"token": "123"}) == "123"
    assert parse_token({"auth_token": "abc"}) == "abc"
    assert parse_token({"data": {"authToken": "xyz"}}) == "xyz"
    assert parse_token({"apiToken": "abc"}) == "abc"
    assert parse_token({"data": {"accessToken": "xyz"}}) == "xyz"
    assert (
        parse_token(
            {
                "metadata": "ignored",
                "empty": {"value": 42},
                "data": {"access_token": "later-token"},
            }
        )
        == "later-token"
    )


@pytest.mark.parametrize("token_data", [137, {"accessToken": True}])
def test_parse_token_rejects_wrong_type(token_data):
    with pytest.raises(RuntimeError, match="wrong type"):
        parse_token(token_data)


def test_parse_token_rejects_missing_token():
    with pytest.raises(RuntimeError, match="no token"):
        parse_token({})


@pytest.mark.parametrize("token_data", ["", {"token": ""}])
def test_parse_token_rejects_empty_token(token_data):
    with pytest.raises(RuntimeError, match="empty"):
        parse_token(token_data)
