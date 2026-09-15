#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx2
import pytest
from authlib.oauth2.rfc6749 import wrappers
from joserfc import jwt
from joserfc.jwk import RSAKey

from cuiman.api.config import ClientConfig


@pytest.fixture(autouse=True)
def block_system_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Require explicit keyring mocks instead of accessing a machine's secrets."""

    def unexpected_access(*_args: object, **_kwargs: object) -> None:
        pytest.fail(
            "Unexpected OS-keyring access: mock credential storage in this test."
        )

    for operation in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(f"keyring.{operation}", unexpected_access)


@pytest.fixture(autouse=True)
def isolate_default_client_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prevent tests from loading a developer's real client configuration."""
    monkeypatch.setattr(ClientConfig, "default_path", tmp_path / "config")


@pytest.fixture
def auth_provider(monkeypatch):
    """Real HTTPX/Authlib pipelines with deterministic provider HTTP and clock."""
    state = SimpleNamespace(
        now=int(time.time()),
        requests=[],
        grants=[],
        replies=[],
        statuses=[],
        nonce=None,
        claims={},
        include_id=True,
        refresh_id=False,
        revoke_status=200,
    )
    key = RSAKey.generate_key(2048)
    state.key = key
    state.metadata = dict(
        issuer="https://identity.test/realm",
        authorization_endpoint="https://identity.test/authorize",
        token_endpoint="https://identity.test/token",
        jwks_uri="https://identity.test/keys",
        revocation_endpoint="https://identity.test/revoke",
    )
    monkeypatch.setattr(wrappers, "time", SimpleNamespace(time=lambda: state.now))

    def handle(request):
        state.requests.append(request)
        if request.url.path.endswith("openid-configuration"):
            assert "authorization" not in request.headers
            return httpx2.Response(200, json=state.metadata)
        if request.url.path == "/keys":
            assert "authorization" not in request.headers
            return httpx2.Response(
                200, json={"keys": [state.key.as_dict(private=False)]}
            )
        if request.url.path == "/revoke":
            return httpx2.Response(state.revoke_status)
        if request.url.path == "/login":
            return httpx2.Response(200, json={"token": "proprietary"})
        if request.url.path == "/token":
            form = parse_qs(request.content.decode())
            state.grants.append(form)
            if state.replies:
                status, body = state.replies.pop(0)
                return httpx2.Response(status, json=body)
            body = dict(
                access_token=f"access-{len(state.grants)}",
                token_type="Bearer",
                expires_in=600,
                scope="processes",
                extra={"kept": True},
            )
            grant = form["grant_type"][0]
            if grant != "client_credentials":
                body["refresh_token"] = f"refresh-{len(state.grants)}"
            if state.include_id and (grant == "authorization_code" or state.refresh_id):
                claims = dict(
                    iss=state.metadata["issuer"],
                    sub="user",
                    aud="client",
                    exp=int(time.time()) + 600,
                    iat=int(time.time()),
                    nonce=state.nonce,
                )
                claims.update(state.claims)
                body["id_token"] = jwt.encode({"alg": "RS256"}, claims, state.key)
            return httpx2.Response(200, json=body)
        return httpx2.Response(
            state.statuses.pop(0) if state.statuses else 200, json={"conformsTo": []}
        )

    state.handle_request = handle

    for cls in (httpx2.Client, httpx2.AsyncClient):
        original = cls.__init__

        def initialize(self, *args, _original=original, **kwargs):
            kwargs.setdefault("transport", httpx2.MockTransport(handle))
            kwargs.setdefault("trust_env", False)
            _original(self, *args, **kwargs)

        monkeypatch.setattr(cls, "__init__", initialize)

    def authorize(server, url, state_value, **kwargs):
        params = parse_qs(httpx2.URL(url).query.decode())
        assert params["code_challenge_method"] == ["S256"]
        assert params["redirect_uri"] == [server.redirect_uri]
        assert params["state"] == [state_value]
        state.nonce = params["nonce"][0]
        return "code"

    monkeypatch.setattr("cuiman.api.client_mixin.authorize", authorize)
    monkeypatch.setattr("cuiman.api.async_client_mixin.authorize", authorize)
    return state
