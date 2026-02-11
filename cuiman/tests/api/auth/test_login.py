from unittest.mock import MagicMock, patch

import pytest

from cuiman.api.auth import AuthConfig, login
from cuiman.api.auth.login import parse_token


def test_login_json_response():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        client_id="my-client",
        client_secret="my-secret",
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        token = login(cfg)

    assert token == "abc123"
    mock_post.assert_called_once_with(
        "https://acme.com/api/auth/login",
        data={
            "grant_type": "password",
            "username": "u",
            "password": "p",
            "client_id": "my-client",
            "client_secret": "my-secret",
        },
    )


def test_login_plaintext_response():
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

    with patch("httpx.Client.post", return_value=mock_response):
        token = login(cfg)

    assert token == "plaintext-token"


def test_login_without_client_credentials():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        token = login(cfg)

    assert token == "abc123"
    mock_post.assert_called_once_with(
        "https://acme.com/api/auth/login",
        data={
            "grant_type": "password",
            "username": "u",
            "password": "p",
        },
    )


def test_login_missing_auth_url():
    cfg = AuthConfig(
        auth_type="login",
        auth_url=None,
        username="max",
        password="1234",
    )

    with pytest.raises(ValueError, match="Authentication URL must be set."):
        login(cfg)


def test_login_missing_user_pass():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        username=None,
        password=None,
    )

    with pytest.raises(
        ValueError,
        match="Username and password must be set for authentication type 'login'.",
    ):
        login(cfg)


def test_parse_token_data_ok():
    assert parse_token("a1b2") == "a1b2"
    assert parse_token({"token": "123"}) == "123"
    assert parse_token({"auth_token": "abc"}) == "abc"
    assert parse_token({"data": {"authToken": "xyz"}}) == "xyz"
    assert parse_token({"apiToken": "abc"}) == "abc"
    assert parse_token({"data": {"accessToken": "xyz"}}) == "xyz"


def test_parse_token_data_fail():
    with pytest.raises(
        RuntimeError,
        match="Login succeeded, but token returned by server has wrong type.",
    ):
        parse_token(137)

    with pytest.raises(
        RuntimeError,
        match="Login succeeded, but token returned by server has wrong type.",
    ):
        parse_token({"accessToken": True})

    with pytest.raises(
        RuntimeError, match="Login succeeded, but no token has been returned by server."
    ):
        parse_token({})

    with pytest.raises(
        RuntimeError, match="Login succeeded, but token returned by server is empty."
    ):
        parse_token("")

    with pytest.raises(
        RuntimeError, match="Login succeeded, but token returned by server is empty."
    ):
        parse_token({"token": ""})
