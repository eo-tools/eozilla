#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

from unittest.mock import MagicMock

import pytest

from cuiman.api.auth import LoginAuthConfig
from cuiman.api.auth.login import (
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
