from unittest.mock import MagicMock, patch

import pytest

from cuiman.api.auth import AuthConfig, AuthType, login


def test_login_json_response():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_response):
        token = login(cfg)

    assert token == "abc123"


def test_login_plaintext_response():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
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


def test_login_missing_user_pass():
    cfg = AuthConfig(
        auth_type="login",
        auth_url="https://acme.com/api/auth/login",
        username=None,
        password=None,
    )

    with pytest.raises(ValueError):
        login(cfg)
