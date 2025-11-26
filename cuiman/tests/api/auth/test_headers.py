import base64

from cuiman.api.auth import get_auth_headers, AuthType, AuthConfig


def test_auth_headers_none():
    cfg = AuthConfig(auth_type=None)
    assert get_auth_headers(cfg) == {}
    cfg = AuthConfig(auth_type="none")
    assert get_auth_headers(cfg) == {}


def test_auth_headers_token_custom_header():
    cfg = AuthConfig(
        auth_type="token",
        token="abc123",
        token_header="X-Auth-Token",
        use_bearer=False,
    )
    assert get_auth_headers(cfg) == {"X-Auth-Token": "abc123"}


def test_auth_headers_token_bearer():
    cfg = AuthConfig(
        auth_type="token",
        token="abc123",
        use_bearer=True,
    )
    assert get_auth_headers(cfg) == {"Authorization": "Bearer abc123"}


def test_auth_headers_login_strategy():
    cfg = AuthConfig(
        auth_type="login",
        token="xyz",
        token_header="X-Token",
    )
    assert get_auth_headers(cfg) == {"X-Token": "xyz"}


def test_auth_headers_api_key():
    cfg = AuthConfig(
        auth_type="api-key",
        api_key="mykey",
        api_key_header="X-API-Key",
    )
    assert get_auth_headers(cfg) == {"X-API-Key": "mykey"}


def test_auth_headers_basic_auth():
    cfg = AuthConfig(
        auth_type="basic",
        username="user",
        password="pass",
    )
    headers = get_auth_headers(cfg)
    assert "Authorization" in headers

    expected = base64.b64encode(b"user:pass").decode()
    assert headers["Authorization"] == f"Basic {expected}"
