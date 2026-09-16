from unittest.mock import patch
from urllib.parse import urlparse

import httpx2
import pytest

from cuiman.api.auth import OidcAuthConfig
from cuiman.api.auth.oidc import (
    CALLBACK_PATH,
    LoopbackCallbackServer,
    discovery_url,
    parse_oidc_discovery,
)


def test_discovery_url():
    assert discovery_url("https://identity.example.test/") == (
        "https://identity.example.test/.well-known/openid-configuration"
    )
    assert discovery_url("https://identity.example.test/tenant") == (
        "https://identity.example.test/tenant/.well-known/openid-configuration"
    )


@pytest.mark.parametrize(
    "change",
    [
        None,
        {"issuer": "https://other.test"},
        {"token_endpoint": "http://identity.test/token"},
        {"jwks_uri": None},
        {"authorization_endpoint": "https:///missing-host"},
        {"revocation_endpoint": "https://user:secret@identity.test/revoke"},
    ],
)
def test_discovery_rejects_untrusted_metadata(change):
    metadata = dict(
        issuer="https://identity.test",
        authorization_endpoint="https://identity.test/authorize",
        token_endpoint="https://identity.test/token",
        jwks_uri="https://identity.test/keys",
    )
    metadata = [] if change is None else {**metadata, **change}
    response = httpx2.Response(
        200,
        json=metadata,
        request=httpx2.Request(
            "GET", "https://identity.test/.well-known/openid-configuration"
        ),
    )
    with pytest.raises(ValueError):
        parse_oidc_discovery(response, "https://identity.test")


def test_issuer_identifier_preserves_empty_path():
    assert (
        str(
            OidcAuthConfig(
                issuer_url="https://identity.test", client_id="client"
            ).issuer_url
        )
        == "https://identity.test"
    )
    with pytest.raises(ValueError):
        discovery_url("http://identity.test")


def test_loopback_callback_server_receives_one_callback():
    with LoopbackCallbackServer() as callback_server:
        assert urlparse(callback_server.redirect_uri).hostname == "127.0.0.1"
        assert urlparse(callback_server.redirect_uri).path == CALLBACK_PATH
        not_found = httpx2.get(callback_server.redirect_uri.removesuffix(CALLBACK_PATH))
        accepted = httpx2.get(f"{callback_server.redirect_uri}?code=code&state=state")
        repeated = httpx2.get(f"{callback_server.redirect_uri}?code=other&state=state")
        parameters = callback_server.wait_for_callback(timeout=1)

    assert not_found.status_code == 404
    assert accepted.status_code == 200
    assert repeated.status_code == 409
    assert parameters == {"code": ["code"], "state": ["state"]}


def test_loopback_callback_server_times_out():
    with LoopbackCallbackServer() as callback_server:
        with pytest.raises(TimeoutError, match="Timed out"):
            callback_server.wait_for_callback(timeout=0)


def test_loopback_callback_server_joins_a_running_thread():
    callback_server = LoopbackCallbackServer()
    callback_server.start()
    with patch.object(callback_server._thread, "is_alive", return_value=True):
        callback_server.close()
