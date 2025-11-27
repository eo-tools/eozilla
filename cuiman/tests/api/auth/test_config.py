import base64

from cuiman.api.auth import AuthConfig


def test_auth_headers_none():
    config = AuthConfig(auth_type=None)
    assert config.auth_headers == {}
    config = AuthConfig(auth_type="none")
    assert config.auth_headers == {}


def test_auth_headers_token_custom_header():
    config = AuthConfig(
        auth_type="token",
        token="abc123",
        token_header="X-Auth-Token",
        use_bearer=False,
    )
    assert config.auth_headers == {"X-Auth-Token": "abc123"}


def test_auth_headers_token_bearer():
    config = AuthConfig(
        auth_type="token",
        token="abc123",
        use_bearer=True,
    )
    assert config.auth_headers == {"Authorization": "Bearer abc123"}


def test_auth_headers_login_strategy():
    config = AuthConfig(
        auth_type="login",
        token="xyz",
        token_header="X-Token",
    )
    assert config.auth_headers == {"X-Token": "xyz"}


def test_auth_headers_api_key():
    config = AuthConfig(
        auth_type="api-key",
        api_key="mykey",
        api_key_header="X-API-Key",
    )
    assert config.auth_headers == {"X-API-Key": "mykey"}


def test_auth_headers_basic_auth():
    config = AuthConfig(
        auth_type="basic",
        username="user",
        password="pass",
    )
    headers = config.auth_headers
    assert "Authorization" in headers

    expected = base64.b64encode(b"user:pass").decode()
    assert headers["Authorization"] == f"Basic {expected}"
