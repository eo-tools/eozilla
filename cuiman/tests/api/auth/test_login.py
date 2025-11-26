from unittest.mock import MagicMock, patch

import pytest
from yourpkg.auth_login import login_and_get_token
from yourpkg.config import AuthStrategy, ClientConfig


def test_login_and_get_token_json_response():
    cfg = ClientConfig(
        base_url="http://api",
        auth_strategy=AuthStrategy.LOGIN,
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
    cfg = ClientConfig(
        base_url="http://api",
        auth_strategy=AuthStrategy.LOGIN,
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
    cfg = ClientConfig(
        base_url="http://api",
        auth_strategy=AuthStrategy.LOGIN,
        username=None,
        password=None,
    )

    with pytest.raises(ValueError):
        login_and_get_token(cfg)
