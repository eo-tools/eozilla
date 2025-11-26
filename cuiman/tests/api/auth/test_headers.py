import base64

from yourpkg.auth_headers import get_auth_headers
from yourpkg.config import AuthStrategy, ClientConfig


def test_auth_headers_none():
    cfg = ClientConfig(base_url="http://x", auth_strategy=AuthStrategy.NONE)
    assert get_auth_headers(cfg) == {}


def test_auth_headers_token_custom_header():
    cfg = ClientConfig(
        base_url="http://x",
        auth_strategy=AuthStrategy.TOKEN,
        token="abc123",
        token_header="X-Auth-Token",
        use_bearer=False,
    )
    assert get_auth_headers(cfg) == {"X-Auth-Token": "abc123"}


def test_auth_headers_token_bearer():
    cfg = ClientConfig(
        base_url="http://x",
        auth_strategy=AuthStrategy.TOKEN,
        token="abc123",
        use_bearer=True,
    )
    assert get_auth_headers(cfg) == {"Authorization": "Bearer abc123"}


def test_auth_headers_login_strategy():
    cfg = ClientConfig(
        base_url="http://x",
        auth_strategy=AuthStrategy.LOGIN,
        token="xyz",
        token_header="X-Token",
    )
    assert get_auth_headers(cfg) == {"X-Token": "xyz"}


def test_auth_headers_api_key():
    cfg = ClientConfig(
        base_url="http://x",
        auth_strategy=AuthStrategy.API_KEY,
        api_key="mykey",
        api_key_header="X-API-Key",
    )
    assert get_auth_headers(cfg) == {"X-API-Key": "mykey"}


def test_auth_headers_basic_auth():
    cfg = ClientConfig(
        base_url="http://x",
        auth_strategy=AuthStrategy.BASIC,
        basic_username="user",
        basic_password="pass",
    )
    headers = get_auth_headers(cfg)
    assert "Authorization" in headers

    expected = base64.b64encode(b"user:pass").decode()
    assert headers["Authorization"] == f"Basic {expected}"
