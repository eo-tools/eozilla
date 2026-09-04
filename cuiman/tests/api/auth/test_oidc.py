#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

# ruff: noqa: S105, S106

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from cuiman.api.auth import OidcAuthConfig, TokenResult
from cuiman.api.auth.oidc import (
    CALLBACK_PATH,
    LoopbackCallbackServer,
    OidcDiscovery,
    build_authorization_url,
    discover_oidc_provider,
    discovery_url,
    exchange_oidc_code,
    generate_pkce_verifier,
    parse_callback_parameters,
    parse_oidc_discovery,
    pkce_challenge,
    prepare_oidc_discovery,
    prepare_oidc_refresh_request,
    renew_oidc_tokens,
)


def make_auth(**kwargs: object) -> OidcAuthConfig:
    return OidcAuthConfig.model_validate(
        {
            "issuer_url": "https://identity.example.test",
            "client_id": "client",
            "scopes": ("profile",),
            "refresh_token": "refresh",
            **kwargs,
        }
    )


def discovery() -> OidcDiscovery:
    return OidcDiscovery(
        issuer="https://identity.example.test/",
        authorization_endpoint="https://identity.example.test/authorize",
        token_endpoint="https://identity.example.test/token",
        revocation_endpoint="https://identity.example.test/revoke",
    )


def response(metadata: object) -> MagicMock:
    result = MagicMock()
    result.json.return_value = metadata
    return result


def test_discovery_url():
    assert discovery_url("https://identity.example.test/") == (
        "https://identity.example.test/.well-known/openid-configuration"
    )
    assert discovery_url("https://identity.example.test/tenant") == (
        "https://identity.example.test/.well-known/openid-configuration/tenant"
    )


def test_prepare_oidc_discovery():
    assert prepare_oidc_discovery(make_auth()) == (
        "https://identity.example.test/",
        "https://identity.example.test/.well-known/openid-configuration",
    )


def test_discover_oidc_provider_requests_and_validates_metadata():
    metadata = {
        "issuer": "https://identity.example.test/",
        "authorization_endpoint": "https://identity.example.test/authorize",
        "token_endpoint": "https://identity.example.test/token",
        "revocation_endpoint": "https://identity.example.test/revoke",
    }
    with patch("httpx.Client.get", return_value=response(metadata)) as get:
        result = discover_oidc_provider(make_auth())

    assert result == discovery()
    get.assert_called_once_with(
        "https://identity.example.test/.well-known/openid-configuration"
    )


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ([], "JSON object"),
        ({}, "issuer"),
        (
            {
                "issuer": "https://another.example.test",
                "authorization_endpoint": "https://identity.example.test/authorize",
                "token_endpoint": "https://identity.example.test/token",
            },
            "issuer does not match",
        ),
        (
            {
                "issuer": "https://identity.example.test/",
                "token_endpoint": "https://identity.example.test/token",
            },
            "authorization_endpoint",
        ),
        (
            {
                "issuer": "https://identity.example.test/",
                "authorization_endpoint": "https://identity.example.test/authorize",
                "token_endpoint": "http://identity.example.test/token",
            },
            "token_endpoint",
        ),
        (
            {
                "issuer": "https://identity.example.test/",
                "authorization_endpoint": "https://identity.example.test/authorize",
                "token_endpoint": "https://identity.example.test/token",
                "revocation_endpoint": "http://identity.example.test/revoke",
            },
            "revocation_endpoint",
        ),
    ],
)
def test_parse_oidc_discovery_rejects_invalid_metadata(metadata, message):
    with pytest.raises(RuntimeError, match=message):
        parse_oidc_discovery(response(metadata), "https://identity.example.test/")


def test_pkce_verifier_and_challenge():
    verifier = generate_pkce_verifier()
    assert len(verifier) >= 43
    assert pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_build_authorization_url_uses_pkce_and_required_scope():
    url = build_authorization_url(
        discovery(),
        make_auth(),
        "http://127.0.0.1:49152/callback",
        "state",
        "verifier",
    )

    assert urlparse(url).path == "/authorize"
    assert parse_qs(urlparse(url).query) == {
        "response_type": ["code"],
        "client_id": ["client"],
        "redirect_uri": ["http://127.0.0.1:49152/callback"],
        "scope": ["openid profile"],
        "state": ["state"],
        "code_challenge": [pkce_challenge("verifier")],
        "code_challenge_method": ["S256"],
    }


@pytest.mark.parametrize(
    ("parameters", "state", "message"),
    [
        ({"error": ["access_denied"]}, "state", "authorization failed"),
        (
            {"error": ["access_denied"], "error_description": ["No thanks"]},
            "state",
            "No thanks",
        ),
        ({"code": ["code"], "state": ["wrong"]}, "state", "state does not match"),
        ({"state": ["state"]}, "state", "authorization code"),
        ({"code": ["one", "two"], "state": ["state"]}, "state", "multiple code"),
    ],
)
def test_parse_callback_parameters_rejects_invalid_values(parameters, state, message):
    with pytest.raises(RuntimeError, match=message):
        parse_callback_parameters(parameters, state)


def test_parse_callback_parameters_returns_code():
    assert (
        parse_callback_parameters({"code": ["code"], "state": ["state"]}, "state")
        == "code"
    )


def test_loopback_callback_server_receives_one_callback():
    with LoopbackCallbackServer() as callback_server:
        assert urlparse(callback_server.redirect_uri).hostname == "127.0.0.1"
        assert urlparse(callback_server.redirect_uri).path == CALLBACK_PATH
        not_found = httpx.get(callback_server.redirect_uri.removesuffix(CALLBACK_PATH))
        accepted = httpx.get(f"{callback_server.redirect_uri}?code=code&state=state")
        repeated = httpx.get(f"{callback_server.redirect_uri}?code=other&state=state")
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


def test_exchange_oidc_code_posts_authorization_code_credentials():
    token_response = response({"access_token": "access", "refresh_token": "refresh"})
    with patch("httpx.Client.post", return_value=token_response) as post:
        result = exchange_oidc_code(
            discovery(),
            make_auth(),
            "code",
            "verifier",
            "http://127.0.0.1:49152/callback",
        )

    assert result == TokenResult(access_token="access", refresh_token="refresh")
    post.assert_called_once_with(
        "https://identity.example.test/token",
        data={
            "grant_type": "authorization_code",
            "code": "code",
            "redirect_uri": "http://127.0.0.1:49152/callback",
            "client_id": "client",
            "code_verifier": "verifier",
        },
    )


def test_renew_oidc_tokens_discovers_provider_and_posts_refresh_token():
    token_response = response({"access_token": "access"})
    with (
        patch("cuiman.api.auth.oidc.discover_oidc_provider", return_value=discovery()),
        patch("httpx.Client.post", return_value=token_response) as post,
    ):
        result = renew_oidc_tokens(make_auth())

    assert result == TokenResult(access_token="access")
    post.assert_called_once_with(
        "https://identity.example.test/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": "refresh",
            "client_id": "client",
        },
    )


def test_renew_oidc_tokens_requires_a_refresh_token():
    with pytest.raises(ValueError, match="refresh token"):
        renew_oidc_tokens(make_auth(refresh_token=None))


def test_prepare_oidc_refresh_request_requires_a_refresh_token():
    with pytest.raises(ValueError, match="refresh token"):
        prepare_oidc_refresh_request(make_auth(refresh_token=None))
