from unittest.mock import MagicMock, patch

import pytest
from cuiman.api.auth import login_and_get_token, AuthConfig, AuthType


def test_login_and_get_token_json_response():
    cfg = AuthConfig(
        type=AuthType.TOKEN,
        auth_url="https://acme.com/api/auth/login",
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.return_value = {"token": "abc123"}
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_response):
        token = login_and_get_token(cfg)

    assert token == "abc123"
    assert cfg.token == "abc123"


def test_login_and_get_token_plaintext_response():
    cfg = AuthConfig(
        type=AuthType.TOKEN,
        auth_url="https://acme.com/api/auth/login",
        username="u",
        password="p",
    )

    mock_response = MagicMock()
    mock_response.json.side_effect = ValueError("not json")
    mock_response.text = "plaintext-token"
    mock_response.raise_for_status.return_value = None

    with patch("httpx.Client.post", return_value=mock_response):
        token = login_and_get_token(cfg)

    assert token == "plaintext-token"
    assert cfg.token == "plaintext-token"


def test_login_and_get_token_missing_user_pass():
    cfg = AuthConfig(
        type=AuthType.TOKEN,
        auth_url="https://acme.com/api/auth/login",
        username=None,
        password=None,
    )

    with pytest.raises(ValueError):
        login_and_get_token(cfg)
