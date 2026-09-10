# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import asyncio
import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

import httpx2
import pytest
from authlib.integrations.base_client.errors import InvalidTokenError, OAuthError
from authlib.oauth2.rfc6749 import wrappers

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import (
    LoginRequiredError,
    OAuth2AuthConfig,
    TokenResult,
    oauth2_client,
    session,
)
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.exceptions import ClientError
from cuiman.api.transport import TransportError


async def invoke(method, **kwargs):
    result = method(**kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def client_type(request):
    return request.param


@pytest.fixture
def provider(monkeypatch):
    state = SimpleNamespace(
        now=1_800_000_000, grants=[], requests=[], responses=[], statuses=[]
    )
    monkeypatch.setattr(wrappers, "time", SimpleNamespace(time=lambda: state.now))

    def handle(request):
        if request.url.host == "identity.example.test":
            assert request.method == "POST"
            assert "authorization" not in request.headers
            state.grants.append(
                {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            )
            status, body = (
                state.responses.pop(0)
                if state.responses
                else (
                    200,
                    dict(
                        access_token=f"access-{len(state.grants)}",
                        refresh_token=f"refresh-{len(state.grants)}",
                        expires_in=120,
                        scope="processes:read",
                        provider_extra={"retained": True},
                    ),
                )
            )
            if isinstance(body, Exception):
                raise body
            return httpx2.Response(status, json=body)
        assert request.url.host == "api.example.test"
        state.requests.append(request)
        return httpx2.Response(
            state.statuses.pop(0) if state.statuses else 200, json={"conformsTo": []}
        )

    options = oauth2_client._options
    monkeypatch.setattr(
        oauth2_client,
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
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.example.test/token",
            "username": "user",
            "password": "password",
            **auth,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "registration",
    [{}, {"client_id": "client"}, {"client_id": "client", "client_secret": "secret"}],
)
@pytest.mark.parametrize("use_bearer", [True, False])
async def test_password_lifecycle_uses_authlib_and_persists_rotation(
    client_type, provider, registration, use_bearer
):
    client = make_client(client_type, **registration, use_bearer=use_bearer)
    saved = []
    client.config.auth.set_secret_persistor(
        lambda auth: saved.append(auth.to_secret_dict())
    )
    assert client.token is None
    try:
        await invoke(client.login)
        runtime = client._oauth_client
        assert client._transport is None
        assert provider.grants == [
            {
                "grant_type": "password",
                "username": "user",
                "password": "password",
                **registration,
            }
        ]
        await invoke(client.get_conformance)
        snapshot = client.token
        snapshot["provider_extra"]["retained"] = False
        assert client.token["provider_extra"]["retained"]
        provider.now += 121
        await invoke(client.get_conformance)
        assert client._oauth_client is runtime
        assert provider.grants[-1] == {
            "grant_type": "refresh_token",
            "refresh_token": "refresh-1",
            **registration,
        }
        assert client.token["refresh_token"] == "refresh-2"
        assert client.token["expires_at"] == provider.now + 120
        assert client.token["scope"] == "processes:read"
        assert len(saved) == 2
        assert json.loads(saved[-1]["oauth_token"]) == client.token
        assert client.config.auth.access_token is client.config.auth.oauth_token is None
        header, prefix = (
            ("authorization", "Bearer ") if use_bearer else ("x-auth-token", "")
        )
        assert [r.headers[header] for r in provider.requests] == [
            prefix + "access-1",
            prefix + "access-2",
        ]
        if not use_bearer:
            assert all("authorization" not in r.headers for r in provider.requests)
        await invoke(client.close)
        await invoke(client.close)
        assert runtime.is_closed and client.token is None
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_refresh_only_bootstrap_needs_no_password(client_type, provider):
    client = make_client(
        client_type, username=None, password=None, refresh_token="bootstrap"
    )
    try:
        await invoke(client.get_conformance)
        assert provider.grants == [
            {"grant_type": "refresh_token", "refresh_token": "bootstrap"}
        ]
        assert client.token["access_token"] == "access-1"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "refresh", [{}, {"refresh_token": None}, {"refresh_token": ""}]
)
async def test_refresh_preserves_omitted_token_but_force_discards_it(
    client_type, provider, refresh
):
    client = make_client(client_type, access_token="old", refresh_token="old-refresh")
    provider.responses = [
        (200, {"access_token": "renewed", **refresh}),
        (200, {"access_token": "fresh", **refresh}),
    ]
    provider.statuses = [401, 200]
    try:
        await invoke(client.get_conformance)
        assert client.token["refresh_token"] == "old-refresh"
        transport, runtime = client._transport, client._oauth_client
        await invoke(client.login, force=True, interactive=False)
        await invoke(client.get_conformance)
        assert client._transport is transport and client._oauth_client is runtime
        assert "refresh_token" not in client.token
        assert provider.requests[-1].headers["authorization"] == "Bearer fresh"
        assert [g["grant_type"] for g in provider.grants] == [
            "refresh_token",
            "password",
        ]
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("when", ["initial", "expiry", "401"])
@pytest.mark.parametrize("credentials", [True, False])
async def test_rejected_refresh_falls_back_once_without_interaction(
    client_type, provider, when, credentials
):
    auth = {"refresh_token": "rejected"}
    if when == "401":
        auth["access_token"] = "old"
        provider.statuses = [401, 200]
    elif when == "expiry":
        auth["oauth_token"] = {
            "access_token": "old",
            "refresh_token": "rejected",
            "expires_at": 1,
        }
    if not credentials:
        auth.update(username=None, password=None)
    client = make_client(client_type, **auth)
    provider.responses = [
        (400, {"error": "invalid_grant"}),
        (200, {"access_token": "fresh"}),
    ]
    try:
        with patch("typer.prompt") as prompt:
            if credentials:
                await invoke(client.get_conformance)
                assert client.token == {"access_token": "fresh"}
                assert provider.requests[-1].headers["authorization"] == "Bearer fresh"
            else:
                with pytest.raises(LoginRequiredError, match=r"login\(force=True\)"):
                    await invoke(client.get_conformance)
            prompt.assert_not_called()
        assert [g["grant_type"] for g in provider.grants] == (
            ["refresh_token", "password"] if credentials else ["refresh_token"]
        )
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("when", ["expiry", "401"])
@pytest.mark.parametrize("credentials", [True, False])
async def test_no_refresh_token_reacquires_or_requires_login(
    client_type, provider, when, credentials
):
    client = make_client(
        client_type,
        oauth_token={
            "access_token": "old",
            **({"expires_at": 1} if when == "expiry" else {}),
        },
        **({} if credentials else {"username": None, "password": None}),
    )
    if when == "401":
        provider.statuses = [401, 200]
    try:
        if credentials:
            await invoke(client.get_conformance)
            assert provider.grants == [
                {"grant_type": "password", "username": "user", "password": "password"}
            ]
        else:
            with pytest.raises(LoginRequiredError):
                await invoke(client.get_conformance)
            assert not provider.grants
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body,error",
    [
        (503, {"error": "invalid_grant"}, httpx2.HTTPStatusError),
        (401, {"error": "invalid_grant"}, OAuthError),
        (200, {"error": "invalid_grant"}, OAuthError),
        (400, {"error": "invalid_client"}, OAuthError),
        (400, [], httpx2.HTTPStatusError),
        (200, [], RuntimeError),
        (200, {"access_token": ""}, RuntimeError),
        (200, {"access_token": "new", "refresh_token": 42}, RuntimeError),
        (200, httpx2.ConnectError("unavailable"), httpx2.ConnectError),
    ],
)
async def test_other_refresh_failures_do_not_fetch_password_or_replace_token(
    client_type, provider, status, body, error
):
    client = make_client(
        client_type,
        oauth_token={
            "access_token": "old",
            "refresh_token": "old-refresh",
            "expires_at": 1,
        },
    )
    persist = Mock()
    client.config.auth.set_secret_persistor(persist)
    try:
        await invoke(client.login)
        previous = client.token
        persist.reset_mock()
        provider.responses = [(status, body)]
        expected = TransportError if issubclass(error, httpx2.HTTPError) else error
        with pytest.raises(expected) as caught:
            await invoke(client.get_conformance)
        if expected is TransportError:
            assert isinstance(caught.value.__cause__, error)
        assert client.token == previous
        assert (
            len(provider.grants) == 1
            and provider.grants[0]["grant_type"] == "refresh_token"
        )
        assert not provider.requests
        persist.assert_not_called()
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("when", ["initial", "expiry", "401"])
async def test_storage_failure_keeps_live_password_token_and_retry_only_saves(
    client_type, provider, when
):
    client = make_client(client_type)
    persist = Mock()
    client.config.auth.set_secret_persistor(persist)
    try:
        if when != "initial":
            await invoke(client.get_conformance)
            if when == "expiry":
                provider.now += 121
            else:
                provider.statuses = [401, 200]
        persist.side_effect = SecretStoreError("unavailable")
        with pytest.warns(oauth2_client.CredentialStorageWarning):
            await invoke(client.get_conformance)
        count = len(provider.grants)
        assert (
            provider.requests[-1].headers["authorization"] == f"Bearer access-{count}"
        )
        persist.side_effect = None
        await invoke(client.login)
        assert len(provider.grants) == count
        assert persist.call_args.args[0].oauth_token == client.token
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override",
    [
        None,
        {"headers": {"Authorization": "external"}},
        {"auth": ("external", "password")},
    ],
)
async def test_401_replay_is_bounded_and_external_credentials_bypass_it(
    client_type, provider, override
):
    client = make_client(client_type, access_token="old", refresh_token="old-refresh")
    provider.statuses = [401, 401]
    try:
        with pytest.raises(ClientError):
            await invoke(client.get_conformance, **(override or {}))
        assert len(provider.requests) == (1 if override else 2)
        assert len(provider.grants) == (0 if override else 1)
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("secret", [None, "secret"])
@pytest.mark.parametrize("fail", [False, True])
async def test_explicit_prompt_and_failed_forced_login_preserve_live_token(
    client_type, provider, secret, fail
):
    client = make_client(
        client_type,
        username=None,
        password=None,
        client_id="client",
        client_secret=secret,
        access_token="old",
    )
    try:
        await invoke(client.get_conformance)
        runtime = client._oauth_client
        if fail:
            provider.responses = [(400, {"error": "invalid_grant"})]
        with patch("typer.prompt", side_effect=["alice", "password"]) as prompt:
            if fail:
                with pytest.raises(OAuthError):
                    await invoke(client.login, force=True)
                assert client.token == {"access_token": "old"}
                assert client.config.auth.username is None
            else:
                await invoke(client.login, force=True)
                assert client.config.auth.username == "alice"
            assert prompt.call_count == 2
        assert provider.grants == [
            {
                "grant_type": "password",
                "username": "alice",
                "password": "password",
                "client_id": "client",
                **({"client_secret": secret} if secret else {}),
            }
        ]
        assert client._oauth_client is runtime
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_file_profile_restores_absolute_expiry_and_saves_prompted_credentials(
    client_type, provider, tmp_path
):
    path = tmp_path / "profile.yaml"
    ClientConfig.new_instance(
        api_url="https://api.example.test",
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.example.test/token",
        },
    ).write(path)
    with (
        patch("cuiman.api.config.load_auth_secrets", return_value={}),
        patch("cuiman.api.config.save_auth_secrets") as save,
        patch("typer.prompt", side_effect=["alice", "password"]),
    ):
        client = client_type(config_path=path)
        try:
            await invoke(client.login)
            saved = save.call_args.args[3]
            assert saved["username"] == "alice" and saved["password"] == "password"
            snapshot = client.token
        finally:
            await invoke(client.close)
    provider.now += 121
    with (
        patch("cuiman.api.config.load_auth_secrets", return_value=saved),
        patch("cuiman.api.config.save_auth_secrets") as save,
    ):
        client = client_type(config_path=path)
        try:
            assert client.config.auth.oauth_token == snapshot
            await invoke(client.get_conformance)
            assert provider.grants[-1] == {
                "grant_type": "refresh_token",
                "refresh_token": "refresh-1",
            }
            assert save.call_args.args[:3] == (
                path,
                "https://api.example.test/",
                "oauth2",
            )
            assert json.loads(save.call_args.args[3]["oauth_token"]) == client.token
            assert "password" not in ClientConfig.read_file_data(path)["auth"]
            assert "oauth_token" not in client.config._repr_json_()[0]["auth"]
        finally:
            await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_legacy_session_consumes_saved_snapshot_without_provider_exchange(
    asynchronous,
):
    auth = OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        oauth_token={
            "access_token": "saved",
            "refresh_token": "refresh",
            "expires_at": 1,
        },
    )
    assert session.can_login(auth)
    operation = (
        session.resolve_auth_headers_async
        if asynchronous
        else session.resolve_auth_headers
    )
    assert await invoke(lambda: operation(auth)) == {"Authorization": "Bearer saved"}
    assert auth.oauth_token is None
    assert auth.access_token == "saved" and auth.refresh_token == "refresh"


@pytest.mark.asyncio
async def test_failed_initial_refresh_can_retry_on_next_api_call(client_type, provider):
    client = make_client(
        client_type, username=None, password=None, refresh_token="bootstrap"
    )
    provider.responses = [(503, {"error": "temporarily_unavailable"})]
    try:
        with pytest.raises(httpx2.HTTPStatusError):
            await invoke(client.get_conformance)
        assert client._transport is None
        await invoke(client.get_conformance)
        assert len(provider.grants) == 2
        assert all(g["grant_type"] == "refresh_token" for g in provider.grants)
        assert provider.requests[-1].headers["authorization"] == "Bearer access-2"
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["grant", "storage"])
async def test_fallback_failure_preserves_the_latest_provider_token(
    client_type, provider, failure
):
    client = make_client(
        client_type,
        oauth_token={
            "access_token": "old",
            "refresh_token": "old-refresh",
            "expires_at": 1,
        },
    )
    persist = Mock()
    client.config.auth.set_secret_persistor(persist)
    try:
        await invoke(client.login)
        persist.reset_mock()
        provider.responses = [
            (400, {"error": "invalid_grant"}),
            (400, {"error": "invalid_grant"})
            if failure == "grant"
            else (200, {"access_token": "fresh"}),
        ]
        if failure == "storage":
            persist.side_effect = RuntimeError("unexpected save failure")
        with pytest.raises(OAuthError if failure == "grant" else RuntimeError):
            await invoke(client.get_conformance)
        assert len(provider.grants) == 2
        assert not provider.requests
        if failure == "grant":
            assert client.token["access_token"] == "old"
            assert client.token["refresh_token"] == "old-refresh"
            persist.assert_not_called()
        else:
            assert client.token == {"access_token": "fresh"}
            assert persist.call_count == 1
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
async def test_unexpected_refresh_callback_error_is_not_password_fallback(provider):
    client = make_client(AsyncClient)
    try:
        await client.login()
        provider.now += 121
        client.config.auth.set_secret_persistor(Mock(side_effect=InvalidTokenError()))
        with pytest.raises(InvalidTokenError):
            await client.get_conformance()
        assert [g["grant_type"] for g in provider.grants] == [
            "password",
            "refresh_token",
        ]
        assert client.token["refresh_token"] == "refresh-2"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cancelled_password_grant_can_retry_without_publishing(provider):
    client = make_client(AsyncClient)
    persist = Mock()
    client.config.auth.set_secret_persistor(persist)
    entered, release = asyncio.Event(), asyncio.Event()

    async def handle(request):
        entered.set()
        await release.wait()
        return httpx2.Response(200, json={"access_token": "fresh"})

    # Inject only the HTTP boundary, retaining the same Authlib lifecycle.
    with patch.object(
        oauth2_client,
        "_options",
        return_value={
            "grant_type": "password",
            "token_endpoint": "https://identity.example.test/token",
            "token_endpoint_auth_method": oauth2_client._no_client_auth,
            "transport": httpx2.MockTransport(handle),
            "trust_env": False,
        },
    ):
        pending = asyncio.create_task(client.login())
        await asyncio.wait_for(entered.wait(), 5)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert client.token is None
        persist.assert_not_called()
        release.set()
        try:
            await client.login()
            assert client.token == {"access_token": "fresh"}
            assert persist.call_count == 1
        finally:
            await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("force", [False, True])
async def test_legacy_snapshot_renewal_and_force_drop_stale_metadata(
    asynchronous, force
):
    auth = OAuth2AuthConfig(
        token_url="https://identity.example.test/token",
        username="user",
        password="password",
        oauth_token={
            "access_token": "saved",
            "refresh_token": "saved-refresh",
            "expires_at": 1,
        },
    )
    persist = Mock()
    auth.set_secret_persistor(persist)
    name = "obtain_oauth2_tokens" if force else "renew_oauth2_tokens"
    if asynchronous:
        name += "_async"
    with patch.object(
        session, name, return_value=TokenResult(access_token="new")
    ) as grant:
        if force:
            operation = (
                session.resolve_auth_headers_async
                if asynchronous
                else session.resolve_auth_headers
            )
            await invoke(lambda: operation(auth, force=True))
        else:
            factory = (
                session.make_async_token_refresher
                if asynchronous
                else session.make_token_refresher
            )
            await invoke(factory(auth))
        assert grant.call_count == 1
    assert auth.oauth_token is None and auth.access_token == "new"
    assert auth.refresh_token == (None if force else "saved-refresh")
    assert "oauth_token" not in persist.call_args.args[0].to_secret_dict()
