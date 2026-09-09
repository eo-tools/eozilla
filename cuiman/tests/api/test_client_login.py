#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import asyncio
import inspect
import threading
from unittest.mock import AsyncMock, Mock, patch

import httpx2
import pytest

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import LoginRequiredError, TokenResult
from cuiman.api.auth.interactive import _wait_for_callback
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.api.auth.session import can_login
from cuiman.api.exceptions import ClientError
from cuiman.cli.config import get_config


async def invoke(method, **kwargs):
    result = method(**kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize(
    "force,reject_retry", [(False, False), (False, True), (True, False)]
)
async def test_recovery_and_forced_login_update_existing_transport(
    client_type, force, reject_retry
):
    client = client_type(
        api_url="https://api.example.test",
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.example.test/token",
            "client_id": "client",
            "username": "user",
            "password": "password",
            "access_token": "old-access",
            "refresh_token": "inactive-refresh",
        },
    )
    calls = []
    saved = []
    client.config.auth.set_secret_persistor(
        lambda auth: saved.append(auth.to_secret_dict())
    )

    def request(method, url, **kwargs):
        if method.upper() == "POST":
            grant = kwargs["data"]["grant_type"]
            calls.append(grant)
            if grant == "refresh_token":
                status, body = (
                    400,
                    {
                        "error": "invalid_grant",
                        "error_description": "Token is not active",
                    },
                )
            else:
                assert grant == "password"
                assert kwargs["data"]["password"] == "password"
                status, body = 200, {"access_token": "fresh-access"}
        else:
            header = kwargs["headers"]["Authorization"]
            calls.append(header)
            status = (
                200 if header == "Bearer fresh-access" and not reject_retry else 401
            )
            body = {"conformsTo": []}
        return httpx2.Response(status, json=body, request=httpx2.Request(method, url))

    with (
        patch("httpx2.Client.request", side_effect=request),
        patch("httpx2.AsyncClient.request", new=AsyncMock(side_effect=request)),
    ):
        transport = await invoke(client._get_transport)
        try:
            if force:
                await invoke(client.login, force=True, interactive=False)
            if reject_retry:
                with pytest.raises(ClientError):
                    await invoke(client.get_conformance)
            else:
                await invoke(client.get_conformance)
            assert client._transport is transport
            assert calls == (
                ["password", "Bearer fresh-access"]
                if force
                else [
                    "Bearer old-access",
                    "refresh_token",
                    "password",
                    "Bearer fresh-access",
                ]
            )
            assert client.config.auth.refresh_token is None
            assert transport.headers == {"Authorization": "Bearer fresh-access"}
            assert saved == [client.config.auth.to_secret_dict()]
        finally:
            await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("interactive", [False, True])
async def test_forced_oidc_login_requires_permitted_interaction(
    client_type, interactive
):
    client = client_type(
        api_url="https://api.example.test",
        auth={
            "auth_type": "oidc",
            "issuer_url": "https://identity.example.test/realm",
            "client_id": "client",
            "access_token": "old-access",
            "refresh_token": "old-refresh",
        },
    )
    auth = client.config.auth
    previous = auth.to_secret_dict()
    candidate = type(auth)(**{**auth.to_public_dict(), "access_token": "fresh-access"})
    prompt_name = "prompt_auth_async" if client_type is AsyncClient else "prompt_auth"
    prompt = (
        AsyncMock(return_value=candidate)
        if client_type is AsyncClient
        else Mock(return_value=candidate)
    )
    with patch(f"cuiman.api.auth.interactive.{prompt_name}", prompt):
        if interactive:
            await invoke(client.login, force=True, no_browser=True)
            assert prompt.call_count == 1
            assert prompt.call_args.kwargs == {"no_browser": True}
            assert auth.access_token == "fresh-access"
            assert auth.refresh_token is None
        else:
            with pytest.raises(LoginRequiredError):
                await invoke(client.login, force=True, interactive=False)
            prompt.assert_not_called()
            assert auth.to_secret_dict() == previous


@pytest.fixture
def requests():
    calls = []

    def request(method, url, **kwargs):
        calls.append((method.upper(), str(url), kwargs))
        if str(url).endswith("openid-configuration"):
            body = {
                "issuer": "https://identity.example.test/realm",
                "authorization_endpoint": "https://identity.example.test/authorize",
                "token_endpoint": "https://identity.example.test/token",
            }
        elif method.upper() == "POST":
            body = {"access_token": "access", "refresh_token": "refresh"}
        else:
            body = {"conformsTo": []}
        return httpx2.Response(200, json=body, request=httpx2.Request(method, url))

    with (
        patch("httpx2.Client.request", side_effect=request),
        patch("httpx2.AsyncClient.request", new=AsyncMock(side_effect=request)),
    ):
        yield calls


AUTH_CASES = [
    dict(auth_type="none"),
    dict(auth_type="basic", username="user", password="password"),
    dict(auth_type="api-key", api_key="key"),
    dict(auth_type="token", access_token="access"),
    dict(
        auth_type="login",
        login_url="https://identity.example.test/login",
        username="user",
        password="password",
    ),
    dict(
        auth_type="oauth2",
        token_url="https://identity.example.test/token",
        username="user",
        password="password",
    ),
    dict(
        auth_type="oauth2",
        token_url="https://identity.example.test/token",
        grant_type="client_credentials",
        client_id="client",
        client_secret="secret",
    ),
    dict(
        auth_type="oauth2",
        token_url="https://identity.example.test/token",
        refresh_token="old-refresh",
    ),
    dict(
        auth_type="oidc",
        issuer_url="https://identity.example.test/realm",
        client_id="client",
        refresh_token="old-refresh",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("auth", AUTH_CASES)
async def test_first_use_authenticates_once(client_type, explicit, auth, requests):
    client = client_type(api_url="https://api.example.test", auth=auth)
    assert client._transport is None
    assert requests == []
    try:
        if explicit:
            assert await invoke(client.login) is None
            assert client._transport is None
        await invoke(client.get_conformance)
        transport = client._transport
        await invoke(client.login)
        await invoke(client.get_conformance)
        assert client._transport is transport
        token_calls = [call for call in requests if call[0] == "POST"]
        assert len(token_calls) == (
            1 if auth["auth_type"] in {"login", "oauth2", "oidc"} else 0
        )
        if token_calls:
            assert requests.index(token_calls[0]) < next(
                i for i, call in enumerate(requests) if "api.example.test" in call[1]
            )
        if "refresh_token" in auth:
            assert token_calls[0][2]["data"]["grant_type"] == "refresh_token"
        for _, url, kwargs in requests:
            if "api.example.test" in url:
                if auth.get("grant_type") == "client_credentials":
                    assert kwargs["auth"] is client._oauth_client.token_auth
                    assert client.token["access_token"] == "access"
                    assert client.config.auth.access_token is None
                else:
                    assert kwargs.get("headers", {}) == client.config.auth_headers
    finally:
        await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize(
    "auth",
    [
        dict(auth_type="token"),
        dict(auth_type="basic"),
        dict(auth_type="api-key"),
        dict(auth_type="login", login_url="https://identity.example.test/login"),
        dict(auth_type="oauth2", token_url="https://identity.example.test/token"),
        dict(
            auth_type="oidc",
            issuer_url="https://identity.example.test/realm",
            client_id="client",
        ),
    ],
)
async def test_missing_credentials_do_not_prompt_or_send_requests(
    client_type, auth, requests
):
    client = client_type(api_url="https://api.example.test", auth=auth)
    with patch("cuiman.api.auth.interactive.prompt_auth") as prompt:
        with pytest.raises(LoginRequiredError, match="client.login"):
            await invoke(client.get_conformance)
        with pytest.raises(LoginRequiredError):
            await invoke(client.login, interactive=False)
        await invoke(client.close)
    prompt.assert_not_called()
    assert requests == []
    assert client._transport is None


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_explicit_login_can_prompt_after_failed_first_call(client_type, requests):
    client = client_type(
        api_url="https://api.example.test", auth=dict(auth_type="basic")
    )
    with pytest.raises(LoginRequiredError):
        await invoke(client.get_conformance)
    with patch("typer.prompt", side_effect=["alice", "password"]) as prompt:
        await invoke(client.login)
        await invoke(client.login)
    assert prompt.call_count == 2
    assert client.config.auth.username == "alice"
    await invoke(client.get_conformance)
    await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_new_file_login_and_refresh_persist_to_same_keyring(
    client_type, tmp_path, requests
):
    path = tmp_path / "profile.yaml"
    ClientConfig.new_instance(
        api_url="https://api.example.test",
        auth=dict(auth_type="oauth2", token_url="https://identity.example.test/token"),
    ).write(path)
    with (
        patch("cuiman.api.config.load_auth_secrets", return_value={}),
        patch("cuiman.api.config.save_auth_secrets") as save,
        patch("typer.prompt", side_effect=["alice", "password"]),
    ):
        # Also exercises wrapping an already-resolved config, as the CLI does.
        config = ClientConfig.create(config_path=path)
        client = client_type(config=config, config_path=path)
        await invoke(client.login)
        assert save.call_count == 1
        await invoke(client.get_conformance)
        refresher = (
            client.config._make_async_token_refresher()
            if client_type is AsyncClient
            else client.config._maybe_make_token_refresher()
        )
        await invoke(refresher)
        assert save.call_count == 2
        assert save.call_args.args[:3] == (path, "https://api.example.test/", "oauth2")
        assert save.call_args.args[3]["refresh_token"] == "refresh"
        assert "password" not in ClientConfig.read_file_data(path)["auth"]
        await invoke(client.close)


@pytest.mark.asyncio
async def test_async_first_requests_share_login(requests):
    client = AsyncClient(api_url="https://api.example.test", auth=AUTH_CASES[4])
    entered, release = asyncio.Event(), asyncio.Event()

    async def login(_):
        entered.set()
        await release.wait()
        return TokenResult(access_token="access")

    with patch("cuiman.api.auth.session.login_async", side_effect=login) as obtain:
        first = asyncio.create_task(client.get_conformance())
        await entered.wait()
        second = asyncio.create_task(client.get_conformance())
        await asyncio.sleep(0)
        assert obtain.call_count == 1
        release.set()
        await asyncio.gather(first, second)
        assert obtain.call_count == 1
    await client.close()


@pytest.mark.asyncio
async def test_cancelled_async_login_is_retryable(requests):
    client = AsyncClient(api_url="https://api.example.test", auth=AUTH_CASES[4])
    entered = asyncio.Event()

    async def login(_):
        entered.set()
        await asyncio.Event().wait()

    with patch("cuiman.api.auth.session.login_async", side_effect=login):
        task = asyncio.create_task(client.get_conformance())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert client._transport is None
    assert client.config.auth.access_token is None
    assert requests == []
    await client.get_conformance()
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_failed_persistence_is_retryable(client_type, requests):
    config = ClientConfig.new_instance(
        api_url="https://api.example.test", auth=AUTH_CASES[4]
    )
    save = Mock(side_effect=[SecretStoreError("unavailable"), None])
    config.auth.set_secret_persistor(save)
    client = client_type(config=config)
    with pytest.raises(SecretStoreError):
        await invoke(client.get_conformance)
    assert client._transport is None
    assert client.config.auth.access_token is None
    assert all("api.example.test" not in call[1] for call in requests)
    await invoke(client.get_conformance)
    assert save.call_count == 2
    await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_injected_token_401_does_not_prompt_refresh_or_use_keyring(
    client_type, monkeypatch
):
    monkeypatch.setenv("EOZILLA_API_URL", "https://api.example.test")
    monkeypatch.setenv("EOZILLA_AUTH__AUTH_TYPE", "token")
    monkeypatch.setenv("EOZILLA_AUTH__ACCESS_TOKEN", "injected-access")
    response = httpx2.Response(
        401,
        json={"type": "about:blank", "title": "Unauthorized", "status": 401},
        request=httpx2.Request("GET", "https://api.example.test/conformance"),
    )
    request = (
        AsyncMock(return_value=response)
        if client_type is AsyncClient
        else Mock(return_value=response)
    )
    target = (
        "httpx2.AsyncClient.request"
        if client_type is AsyncClient
        else "httpx2.Client.request"
    )
    with (
        patch(target, request),
        patch("cuiman.api.config.load_auth_secrets") as load,
        patch("cuiman.api.config.save_auth_secrets") as save,
        patch("cuiman.api.auth.interactive.prompt_auth") as prompt,
        patch("cuiman.api.auth.interactive.prompt_auth_async") as prompt_async,
    ):
        client = client_type()
        try:
            with pytest.raises(ClientError):
                await invoke(client.get_conformance)
            request.assert_called_once()
            assert request.call_args.kwargs["headers"] == {
                "Authorization": "Bearer injected-access"
            }
            assert client.config.auth.access_token == "injected-access"
            load.assert_not_called()
            save.assert_not_called()
            prompt.assert_not_called()
            prompt_async.assert_not_called()
        finally:
            await invoke(client.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_refresh_persistence_failure_does_not_retry_with_unsaved_tokens(
    client_type, requests
):
    config = ClientConfig.new_instance(
        api_url="https://api.example.test",
        auth={**AUTH_CASES[7], "access_token": "old-access"},
    )
    save = Mock(side_effect=SecretStoreError("unavailable"))
    config.auth.set_secret_persistor(save)
    client = client_type(config=config)
    try:
        await invoke(client.get_conformance)
        transport = client._transport
        previous_headers = dict(transport.headers)
        response = httpx2.Response(
            401,
            json={"type": "about:blank", "title": "Unauthorized", "status": 401},
            request=httpx2.Request("GET", "https://api.example.test/conformance"),
        )
        asynchronous = client_type is AsyncClient
        request = (
            AsyncMock(return_value=response)
            if asynchronous
            else Mock(return_value=response)
        )
        http_client = transport.async_httpx2 if asynchronous else transport.sync_httpx2
        with patch.object(http_client, "request", request):
            with pytest.raises(SecretStoreError, match="unavailable"):
                await invoke(client.get_conformance)
        request.assert_called_once()
        save.assert_called_once()
        assert transport.headers == previous_headers
        assert client.config.auth.access_token == "old-access"
        assert client.config.auth.refresh_token == "old-refresh"
    finally:
        await invoke(client.close)


def test_cli_accepts_client_credentials_and_does_not_consult_keyring(
    tmp_path, monkeypatch
):
    path = tmp_path / "config.yaml"
    auth = AUTH_CASES[6]
    ClientConfig.new_instance(api_url="https://api.example.test", auth=auth).write(path)
    monkeypatch.setenv("EOZILLA_AUTH__CLIENT_SECRET", "secret")
    with patch("cuiman.api.config.load_auth_secrets") as load:
        config = get_config(path)
        assert can_login(config.auth)
        load.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("no_browser", [False, True])
async def test_explicit_oidc_login_uses_browser_flow(client_type, no_browser, requests):
    client = client_type(
        api_url="https://api.example.test",
        auth=dict(
            auth_type="oidc",
            issuer_url="https://identity.example.test/realm",
            client_id="client",
        ),
    )
    with (
        patch("cuiman.api.auth.interactive.LoopbackCallbackServer") as server,
        patch(
            "cuiman.api.auth.interactive.webbrowser.open", return_value=True
        ) as browser,
        patch(
            "cuiman.api.auth.interactive.secrets.token_urlsafe", return_value="state"
        ),
    ):
        callback = server.return_value.__enter__.return_value
        callback.redirect_uri = "http://127.0.0.1:12345/callback"
        callback.wait_for_callback.return_value = {"code": ["code"], "state": ["state"]}
        await invoke(client.login, no_browser=no_browser)
        assert browser.call_count == (0 if no_browser else 1)
        server.return_value.__exit__.assert_called_once()
        assert client.config.auth.access_token == "access"
        assert client.config.auth.refresh_token == "refresh"
        await invoke(client.get_conformance)
        await invoke(client.close)


@pytest.mark.asyncio
async def test_cancelled_oidc_interaction_stops_worker(requests):
    client = AsyncClient(
        api_url="https://api.example.test",
        auth=dict(
            auth_type="oidc",
            issuer_url="https://identity.example.test/realm",
            client_id="client",
        ),
    )
    entered, ended = threading.Event(), threading.Event()

    def browser_login(auth, *, no_browser, cancelled):
        entered.set()
        assert cancelled.wait(5)
        ended.set()
        return auth.model_copy(update={"access_token": "too-late"})

    with patch("cuiman.api.auth.interactive._login_oidc", side_effect=browser_login):
        task = asyncio.create_task(client.login())
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(ended.wait, 5)
    assert client.config.auth.access_token is None
    assert client._transport is None
    assert requests == []


def test_cancellable_callback_wait_retries_and_times_out():
    server = Mock()
    server.wait_for_callback.side_effect = [TimeoutError(), {"code": ["code"]}]
    assert _wait_for_callback(server, threading.Event()) == {"code": ["code"]}
    with patch("cuiman.api.auth.interactive.time.monotonic", side_effect=[0, 301]):
        with pytest.raises(TimeoutError, match="OIDC authorization"):
            _wait_for_callback(server, threading.Event())
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(asyncio.CancelledError):
        _wait_for_callback(server, cancelled)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_acquisition_failure_can_be_retried(client_type, requests):
    client = client_type(api_url="https://api.example.test", auth=AUTH_CASES[4])
    name = "login_async" if client_type is AsyncClient else "login"
    with patch(
        "cuiman.api.auth.session." + name, side_effect=RuntimeError("login failed")
    ):
        with pytest.raises(RuntimeError, match="login failed"):
            await invoke(client.get_conformance)
    assert requests == []
    assert client._transport is None
    await invoke(client.get_conformance)
    await invoke(client.close)


def test_secret_persistor_is_not_carried_to_another_endpoint():
    config = ClientConfig.new_instance(
        api_url="https://api.example.test", auth=AUTH_CASES[3]
    )
    persist = Mock()
    config.auth.set_secret_persistor(persist)
    client = Client(config=config, api_url="https://other.example.test")
    client.config.auth.persist_secrets()
    persist.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_missing_client_secret_requires_configuration(client_type, requests):
    auth = {
        key: value for key, value in AUTH_CASES[6].items() if key != "client_secret"
    }
    client = client_type(api_url="https://api.example.test", auth=auth)
    with patch("typer.prompt") as prompt:
        with pytest.raises(ValueError, match="environment variables"):
            await invoke(client.login)
    prompt.assert_not_called()
    assert requests == []
    assert client._transport is None


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("client_secret", [None, "configured-secret"])
async def test_password_login_only_prompts_for_user_credentials(
    client_type, client_secret, requests
):
    client = client_type(
        api_url="https://api.example.test",
        auth=dict(
            auth_type="oauth2",
            token_url="https://identity.example.test/token",
            grant_type="password",
            client_id="client",
            client_secret=client_secret,
        ),
    )
    with patch("typer.prompt", side_effect=["alice", "password"]) as prompt:
        await invoke(client.login)
    assert [call.args[0] for call in prompt.call_args_list] == ["Username", "Password"]
    data = next(call[2]["data"] for call in requests if call[0] == "POST")
    assert data["client_id"] == "client"
    assert data["username"] == "alice"
    assert data["password"] == "password"
    if client_secret is None:
        assert "client_secret" not in data
    else:
        assert data["client_secret"] == client_secret
    assert client.config.auth.client_secret == client_secret
    await invoke(client.close)
