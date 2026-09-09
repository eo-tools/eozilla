# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs

import httpx2
import pytest
from authlib.integrations.base_client.errors import OAuthError
from authlib.oauth2.rfc6749 import wrappers
from pydantic import ValidationError

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import OAuth2AuthConfig
from cuiman.api.auth import client_credentials as cc
from cuiman.api.auth.interactive import prompt_auth
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.exceptions import ClientError


async def invoke(method, **kwargs):
    result = method(**kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def client_type(request):
    return request.param


@pytest.fixture
def provider(monkeypatch):
    """Inject mock HTTP only; retain Authlib's real request and signing pipeline."""
    state = SimpleNamespace(
        now=1_800_000_000, grants=[], requests=[], responses=[], statuses=[]
    )
    monkeypatch.setattr(wrappers, "time", SimpleNamespace(time=lambda: state.now))

    def handle(request):
        if request.url.host == "identity.example.test":
            assert request.method == "POST"
            assert "authorization" not in request.headers
            data = parse_qs(request.content.decode())
            assert data == {
                "grant_type": ["client_credentials"],
                "client_id": ["client"],
                "client_secret": ["secret"],
            }
            state.grants.append(data)
            status, body = (
                state.responses.pop(0)
                if state.responses
                else (
                    200,
                    dict(
                        access_token=f"access-{len(state.grants)}",
                        refresh_token="must-ignore",
                        expires_in=120,
                        token_type="Bearer",
                        scope="processes:read",
                        provider_extra={"value": "retained"},
                    ),
                )
            )
            return httpx2.Response(status, json=body)
        assert request.url.host == "api.example.test"
        state.requests.append(request)
        return httpx2.Response(
            state.statuses.pop(0) if state.statuses else 200,
            json={"conformsTo": []},
        )

    options = cc._options
    monkeypatch.setattr(
        cc,
        "_options",
        lambda auth: {
            **options(auth),
            "transport": httpx2.MockTransport(handle),
            "trust_env": False,
        },
    )
    return state


def make_client(client_type, **auth):
    return client_type(
        api_url="https://api.example.test",
        auth=dict(
            auth_type="oauth2",
            token_url="https://identity.example.test/token",
            grant_type="client_credentials",
            client_id="client",
            client_secret="secret",
            **auth,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("use_bearer", [False, True])
async def test_persistent_client_owns_expiry_signing_and_snapshot(
    client_type, provider, explicit, use_bearer
):
    client = make_client(client_type, use_bearer=use_bearer)
    saved = []
    client.config.auth.set_secret_persistor(
        lambda auth: saved.append(auth.to_secret_dict())
    )
    assert client.token is None
    assert provider.grants == []
    try:
        if explicit:
            await invoke(client.login)
            assert client._transport is None
        await invoke(client.get_conformance)
        runtime = client._oauth_client
        assert len(saved) == 1
        assert client.config.auth.access_token is None
        assert client.config.auth.oauth_token is None
        assert client.token["access_token"] == "access-1"
        snapshot = client.token
        snapshot["provider_extra"]["value"] = "changed"
        assert client.token["provider_extra"]["value"] == "retained"

        provider.now += 121
        await invoke(client.get_conformance)
        assert client._oauth_client is runtime
        assert len(provider.grants) == 2
        assert len(saved) == 2
        token = client.token
        assert "refresh_token" not in token
        assert token["expires_at"] == provider.now + 120
        assert token["scope"] == "processes:read"
        assert json.loads(saved[-1]["oauth_token"]) == token
        assert "access_token" not in saved[-1]
        assert "refresh_token" not in saved[-1]
        header = "authorization" if use_bearer else "x-auth-token"
        prefix = "Bearer " if use_bearer else ""
        assert [r.headers[header] for r in provider.requests] == [
            prefix + "access-1",
            prefix + "access-2",
        ]
        if not use_bearer:
            assert all("authorization" not in r.headers for r in provider.requests)
        transport = client._transport
        closing = "aclose" if client_type is AsyncClient else "close"
        with patch.object(runtime, closing, wraps=getattr(runtime, closing)) as close:
            await invoke(client.close)
            await invoke(client.close)
            assert close.call_count == 1
        assert runtime.is_closed
        assert transport.sync_httpx2 is None and transport.async_httpx2 is None
        assert client.token is None
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_at", ["initial", "renewal"])
async def test_storage_outage_warns_and_retry_saves_without_reauthentication(
    client_type, provider, failure_at
):
    client = make_client(client_type)
    persist = Mock()
    client.config.auth.set_secret_persistor(persist)
    try:
        if failure_at == "renewal":
            await invoke(client.get_conformance)
            provider.now += 121
        persist.side_effect = SecretStoreError("unavailable")
        with pytest.warns(cc.CredentialStorageWarning, match="Credentials are active"):
            await invoke(client.get_conformance)
        grants = len(provider.grants)
        assert (
            provider.requests[-1].headers["authorization"] == f"Bearer access-{grants}"
        )
        assert client.token["access_token"] == f"access-{grants}"
        persist.side_effect = None
        await invoke(client.login)
        assert len(provider.grants) == grants
        assert persist.call_args.args[0].oauth_token == client.token
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("reject_retry", [False, True])
async def test_resource_401_reacquires_once_with_same_client(
    client_type, provider, reject_retry
):
    client = make_client(client_type, access_token="expired-without-metadata")
    provider.statuses = [401, 401 if reject_retry else 200]
    try:
        if reject_retry:
            with pytest.raises(ClientError):
                await invoke(client.get_conformance)
        else:
            await invoke(client.get_conformance)
        assert len(provider.grants) == 1
        assert [r.headers["authorization"] for r in provider.requests] == [
            "Bearer expired-without-metadata",
            "Bearer access-1",
        ]
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override",
    [
        {"headers": {"Authorization": "Bearer external"}},
        {"auth": ("external", "password")},
    ],
)
async def test_per_request_credentials_bypass_renewal(client_type, provider, override):
    client = make_client(client_type, access_token="original")
    provider.statuses = [401]
    try:
        with pytest.raises(ClientError):
            await invoke(client.get_conformance, **override)
        assert provider.grants == []
        assert len(provider.requests) == 1
        assert provider.requests[0].headers["authorization"] != "Bearer original"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_forced_login_and_login_only_close(client_type, provider):
    client = make_client(client_type)
    try:
        await invoke(client.login)
        runtime = client._oauth_client
        assert client._transport is None
        await invoke(client.login, force=True)
        assert client._oauth_client is runtime
        assert client.token["access_token"] == "access-2"
        assert not provider.requests
    finally:
        await invoke(client.close)
    assert runtime.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body,error",
    [
        (400, {"error": "invalid_client"}, OAuthError),
        (503, {"error": "invalid_client"}, httpx2.HTTPStatusError),
        (401, {"access_token": "not-success"}, httpx2.HTTPStatusError),
        (200, {"error": "invalid_client"}, OAuthError),
        (200, [], RuntimeError),
        (200, {}, RuntimeError),
        (200, {"access_token": ""}, RuntimeError),
    ],
)
async def test_acquisition_failure_is_retryable_and_never_publishes_invalid_token(
    client_type, provider, status, body, error
):
    client = make_client(client_type)
    provider.responses = [(status, body)]
    persist = Mock()
    client.config.auth.set_secret_persistor(persist)
    try:
        with pytest.raises(error):
            await invoke(client.login)
        assert client.token is None
        assert client._transport is None
        persist.assert_not_called()
        await invoke(client.get_conformance)
        assert client.token["access_token"] == "access-2"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_close_releases_auth_even_when_injected_transport_close_fails(
    client_type, provider
):
    client = make_client(client_type)
    await invoke(client.login)
    runtime = client._oauth_client
    client._transport = SimpleNamespace(
        close=Mock(side_effect=RuntimeError("close failed")),
        async_close=AsyncMock(side_effect=RuntimeError("close failed")),
    )
    with pytest.raises(RuntimeError, match="close failed"):
        await invoke(client.close)
    assert runtime.is_closed
    await invoke(client.close)


@pytest.mark.asyncio
async def test_keyring_snapshot_restores_absolute_expiry_and_stays_out_of_public_config(
    client_type, provider, monkeypatch, tmp_path
):
    path = tmp_path / "config.yaml"
    public = ClientConfig.new_instance(
        api_url="https://api.example.test",
        auth=dict(
            auth_type="oauth2",
            token_url="https://identity.example.test/token",
            grant_type="client_credentials",
            client_id="client",
        ),
    )
    public.write(path)
    snapshot = dict(
        access_token="stored",
        expires_at=provider.now + 120,
        expires_in=120,
        scope="read",
    )
    loaded = {"client_secret": "secret", "oauth_token": json.dumps(snapshot)}
    load = Mock(return_value=loaded)
    save = Mock()
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", load)
    monkeypatch.setattr("cuiman.api.config.save_auth_secrets", save)
    client = client_type(config_path=path)
    try:
        await invoke(client.get_conformance)
        assert not provider.grants
        assert client.token["expires_at"] == snapshot["expires_at"]
        assert provider.requests[-1].headers["authorization"] == "Bearer stored"
        assert load.call_count == 1
        assert save.call_args.args[:3] == (path, "https://api.example.test/", "oauth2")
        assert (
            json.loads(save.call_args.args[3]["oauth_token"])["expires_at"]
            == snapshot["expires_at"]
        )
        data, _ = client._repr_json_()
        assert "oauth_token" not in data["auth"]
        assert "client_secret" not in data["auth"]
        assert "stored" not in path.read_text()
        assert client.config.auth.oauth_token == snapshot
    finally:
        await invoke(client.close)


def test_explicit_access_token_discards_bootstrap_metadata():
    auth = OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        grant_type="client_credentials",
        client_id="client",
        access_token="override",
        oauth_token={"access_token": "old", "expires_at": 1},
    )
    assert auth.oauth_token is None


@pytest.mark.parametrize(
    "snapshot", [{}, {"access_token": ""}, {"access_token": 42}, "not JSON"]
)
def test_invalid_snapshot_is_rejected(snapshot):
    with pytest.raises(ValidationError):
        OAuth2AuthConfig(
            token_url="https://identity.example.test/token",
            grant_type="client_credentials",
            client_id="client",
            oauth_token=snapshot,
        )


def test_password_snapshot_is_not_silently_used_by_legacy_lifecycle():
    with pytest.raises(ValidationError, match="client_credentials"):
        OAuth2AuthConfig(
            token_url="https://identity.example.test/token",
            oauth_token={"access_token": "token"},
        )


def test_legacy_prompt_helper_does_not_prompt_for_client_credentials():
    auth = OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        grant_type="client_credentials",
        client_id="client",
    )
    with patch("typer.prompt") as prompt:
        with pytest.raises(ValueError, match="environment variables"):
            prompt_auth(auth)
    prompt.assert_not_called()
