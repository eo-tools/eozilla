"""Deterministic ownership tests through real Authlib clients and blocked HTTP."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import httpx2
import pytest

from cuiman import AsyncClient, Client


@pytest.fixture
def controlled_provider(auth_provider, monkeypatch):
    gate = SimpleNamespace(
        path=None,
        entered=threading.Event(),
        release=threading.Event(),
        async_entered=asyncio.Event(),
        async_release=asyncio.Event(),
        cancelled=threading.Event(),
    )

    def send(request):
        if request.url.path == gate.path:
            gate.entered.set()
            assert gate.release.wait(5), "HTTP gate was not released"
        return auth_provider.handle_request(request)

    async def async_send(request):
        if request.url.path == gate.path:
            gate.entered.set()
            gate.async_entered.set()
            try:
                await asyncio.wait_for(gate.async_release.wait(), 5)
            except asyncio.CancelledError:
                gate.cancelled.set()
                raise
        return auth_provider.handle_request(request)

    for cls, handler in ((httpx2.Client, send), (httpx2.AsyncClient, async_send)):
        original = cls.__init__

        def initialize(self, *args, _original=original, _handler=handler, **kwargs):
            kwargs.setdefault("transport", httpx2.MockTransport(_handler))
            _original(self, *args, **kwargs)

        monkeypatch.setattr(cls, "__init__", initialize)
    return gate


def make_owner(kind):
    return kind(
        api_url="https://processing.test",
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.test/token",
            "client_id": "client",
            "username": "user",
            "password": "password",
        },
    )


async def call(owner, method, **kwargs):
    operation = getattr(owner, method)
    if isinstance(owner, AsyncClient):
        return await operation(**kwargs)
    return await asyncio.to_thread(operation, **kwargs)


async def wait_for_http(owner, gate):
    if isinstance(owner, AsyncClient):
        await asyncio.wait_for(gate.async_entered.wait(), 3)
    else:
        assert await asyncio.to_thread(gate.entered.wait, 3)


def release_http(gate):
    gate.path = None
    gate.release.set()
    gate.async_release.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["login", "close", "logout"])
async def test_cancelled_waiting_operation_does_not_mutate_active_owner(
    operation, controlled_provider, auth_provider, monkeypatch
):
    owner = make_owner(AsyncClient)
    await owner.login(interactive=False)
    runtime, token = owner._http_client, owner.token
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    gate = controlled_provider
    gate.path = "/conformance"
    request = asyncio.create_task(owner.get_conformance())
    await wait_for_http(owner, gate)
    logout = asyncio.create_task(getattr(owner, operation)())
    await asyncio.sleep(0)  # Let the operation reach the already-held owner lock.
    logout.cancel()
    await asyncio.sleep(0)
    try:
        assert not owner._closed
        assert owner.token == token
        assert not runtime.is_closed
        deleted.assert_not_called()
    finally:
        release_http(gate)
        await request
        with pytest.raises(asyncio.CancelledError):
            await logout
        await owner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [Client, AsyncClient])
async def test_overlapping_initial_requests_and_refresh_use_one_grant(
    kind, controlled_provider, auth_provider
):
    owner = make_owner(kind)
    gate = controlled_provider
    try:
        for expected_grants in (1, 2):
            gate.path = "/token"
            gate.entered.clear()
            gate.release.clear()
            gate.async_entered.clear()
            gate.async_release.clear()
            first = asyncio.create_task(call(owner, "get_conformance"))
            await wait_for_http(owner, gate)
            others = [
                asyncio.create_task(call(owner, "get_conformance")) for _ in range(4)
            ]
            await asyncio.sleep(0)
            release_http(gate)
            await asyncio.wait_for(asyncio.gather(first, *others), 5)
            assert len(auth_provider.grants) == expected_grants
            resources = [
                r for r in auth_provider.requests if r.url.path == "/conformance"
            ]
            assert all(
                r.headers["Authorization"] == f"Bearer access-{expected_grants}"
                for r in resources[-5:]
            )
            auth_provider.now += 601
        assert auth_provider.grants[-1]["refresh_token"] == ["refresh-1"]
    finally:
        release_http(gate)
        await call(owner, "close")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [Client, AsyncClient])
async def test_close_waits_for_active_request_and_rejects_following_calls(
    kind, controlled_provider
):
    owner = make_owner(kind)
    await call(owner, "login", interactive=False)
    runtime = owner._http_client
    gate = controlled_provider
    gate.path = "/conformance"
    request = asyncio.create_task(call(owner, "get_conformance"))
    await wait_for_http(owner, gate)
    close = asyncio.create_task(call(owner, "close"))
    await asyncio.sleep(0)
    assert not close.done()
    assert not runtime.is_closed
    release_http(gate)
    await asyncio.wait_for(asyncio.gather(request, close), 5)
    assert runtime.is_closed
    with pytest.raises(RuntimeError, match="closed"):
        await call(owner, "get_conformance")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/token", "/conformance"])
async def test_cancelled_active_request_releases_owner_for_retry(
    path, controlled_provider, auth_provider
):
    owner = make_owner(AsyncClient)
    await owner.login(interactive=False)
    if path == "/token":
        auth_provider.now += 601
    gate = controlled_provider
    gate.path = path
    request = asyncio.create_task(owner.get_conformance())
    await wait_for_http(owner, gate)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    release_http(gate)
    await asyncio.wait_for(owner.get_conformance(), 3)
    assert not owner._closed
    assert owner.token["access_token"] == (
        "access-2" if path == "/token" else "access-1"
    )
    await owner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_logout_after_revocation_starts_finishes_cleanup_even_when_cancelled(
    cancel, controlled_provider, auth_provider, monkeypatch
):
    owner = AsyncClient(
        api_url="https://processing.test",
        auth={
            "auth_type": "oidc",
            "issuer_url": "https://identity.test/realm",
            "client_id": "client",
        },
    )
    await owner.login()
    runtime = owner._http_client
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    gate = controlled_provider
    gate.path = "/revoke"
    logout = asyncio.create_task(owner.logout())
    await wait_for_http(owner, gate)
    queued_request = asyncio.create_task(owner.get_conformance())
    if cancel:
        logout.cancel()
        with pytest.raises(asyncio.CancelledError):
            await logout
    else:
        release_http(gate)
        await logout
    with pytest.raises(RuntimeError, match="closed"):
        await queued_request
    assert runtime.is_closed
    assert owner.token is None
    deleted.assert_called_once()
    assert not any(r.url.path == "/conformance" for r in auth_provider.requests)


@pytest.mark.asyncio
async def test_sync_logout_finishes_cleanup_before_queued_request(
    controlled_provider, monkeypatch
):
    owner = Client(
        api_url="https://processing.test",
        auth={
            "auth_type": "oidc",
            "issuer_url": "https://identity.test/realm",
            "client_id": "client",
        },
    )
    await call(owner, "login")
    runtime = owner._http_client
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    gate = controlled_provider
    gate.path = "/revoke"
    logout = asyncio.create_task(call(owner, "logout"))
    await wait_for_http(owner, gate)
    queued = asyncio.create_task(call(owner, "get_conformance"))
    release_http(gate)
    await logout
    with pytest.raises(RuntimeError, match="closed"):
        await queued
    assert runtime.is_closed
    deleted.assert_called_once()


@pytest.mark.asyncio
async def test_cancelled_foreign_loop_proxy_call_cancels_async_http(
    controlled_provider, auth_provider
):
    owner = make_owner(AsyncClient)
    await owner.login(interactive=False)
    callback = owner._app_callbacks()["request"]
    gate = controlled_provider
    gate.path = "/conformance"

    async def browse():
        request = asyncio.create_task(
            callback("GET", "https://processing.test/conformance")
        )
        assert await asyncio.to_thread(gate.entered.wait, 3)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request

    await asyncio.to_thread(lambda: asyncio.run(browse()))
    assert await asyncio.to_thread(gate.cancelled.wait, 3)
    release_http(gate)
    await owner.get_conformance()
    assert len([r for r in auth_provider.requests if r.url.path == "/conformance"]) == 1
    await owner.close()


@pytest.mark.asyncio
async def test_cancelled_sync_proxy_wait_does_not_interrupt_worker_or_race_close(
    controlled_provider, auth_provider
):
    owner = make_owner(Client)
    await call(owner, "login", interactive=False)
    runtime = owner._http_client
    gate = controlled_provider
    gate.path = "/conformance"
    request = asyncio.create_task(
        owner._app_callbacks()["request"]("GET", "https://processing.test/conformance")
    )
    await wait_for_http(owner, gate)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    closing = threading.Event()

    def close():
        closing.set()
        owner.close()

    close_task = asyncio.create_task(asyncio.to_thread(close))
    assert await asyncio.to_thread(closing.wait, 3)
    assert not runtime.is_closed
    release_http(gate)
    await close_task
    assert runtime.is_closed
    assert len([r for r in auth_provider.requests if r.url.path == "/conformance"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [Client, AsyncClient])
async def test_two_browsers_overlap_api_refresh_on_one_owner(
    kind, controlled_provider, auth_provider
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from cuiman.app import App
    from cuiman.app.launch import (
        LAUNCH_ENDPOINT,
        SERVICE_PROXY_ENDPOINT,
        LaunchedAppService,
    )

    owner = make_owner(kind)
    await call(owner, "login", interactive=False)
    runtime = owner._http_client
    service = LaunchedAppService(
        App.create_remote_store(), owner.config, **owner._app_callbacks()
    )
    app = FastAPI()
    service._init_app(app)
    gate = controlled_provider
    try:
        with TestClient(app) as first, TestClient(app) as second:
            for browser in (first, second):
                response = await asyncio.to_thread(
                    browser.post,
                    LAUNCH_ENDPOINT,
                    json={"launch": service.create_launch_code()},
                )
                assert response.status_code == 204
            assert len(service._sessions) == 2
            auth_provider.now += 601
            gate.path = "/token"
            api = asyncio.create_task(call(owner, "get_conformance"))
            await wait_for_http(owner, gate)
            started = [threading.Event(), threading.Event()]

            def request(browser, event):
                event.set()
                return browser.get(SERVICE_PROXY_ENDPOINT + "/conformance")

            browsers = [
                asyncio.create_task(asyncio.to_thread(request, browser, event))
                for browser, event in zip((first, second), started)
            ]
            for event in started:
                assert await asyncio.to_thread(event.wait, 3)
            release_http(gate)
            results = await asyncio.wait_for(asyncio.gather(api, *browsers), 5)
            assert all(response.status_code == 200 for response in results[1:])
            assert len(auth_provider.grants) == 2
            resources = [
                r for r in auth_provider.requests if r.url.path == "/conformance"
            ]
            assert len(resources) == 3
            assert all(
                r.headers["Authorization"] == "Bearer access-2" for r in resources
            )
            assert owner._http_client is runtime
        assert not runtime.is_closed
        await call(owner, "get_conformance")
    finally:
        release_http(gate)
        await call(owner, "close")


@pytest.mark.asyncio
async def test_cancelled_oidc_key_fetch_discards_unverified_refresh(
    controlled_provider, auth_provider
):
    from cuiman.api.auth import LoginRequiredError

    owner = AsyncClient(
        api_url="https://processing.test",
        auth={
            "auth_type": "oidc",
            "issuer_url": "https://identity.test/realm",
            "client_id": "client",
        },
    )
    await owner.login()
    saved = Mock()
    owner.config.auth.set_secret_persistor(saved)
    auth_provider.refresh_id = True
    auth_provider.now += 601
    gate = controlled_provider
    gate.path = "/keys"
    request = asyncio.create_task(owner.get_conformance())
    await wait_for_http(owner, gate)
    assert owner.token["access_token"] == "access-2"
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert owner.token is None
    saved.assert_not_called()
    assert not any(r.url.path == "/conformance" for r in auth_provider.requests)
    with pytest.raises(LoginRequiredError):
        await owner.get_conformance()
    release_http(gate)
    await owner.login()
    saved.assert_called_once()
    assert owner.token["access_token"] == "access-3"
    await owner.close()


@pytest.mark.asyncio
async def test_standalone_app_shutdown_waits_for_its_active_refresh(
    controlled_provider, auth_provider, monkeypatch
):
    import importlib

    from cuiman.app import App
    from cuiman.app.launch import LAUNCH_ENDPOINT, SERVICE_PROXY_ENDPOINT

    serve = importlib.import_module("cuiman.app.serve")
    captured = {}

    def start(service, **kwargs):
        captured.update(service=service, **kwargs)
        return Mock()

    monkeypatch.setattr(serve.rs, "serve", start)
    config = make_owner(Client).config
    serve.serve(config, App.create_remote_store(), display="none")
    app, service = captured["app"], captured["service"]
    ready, stop = asyncio.Event(), asyncio.Event()

    async def lifespan():
        async with app.router.lifespan_context(app):
            ready.set()
            await stop.wait()

    server = asyncio.create_task(lifespan())
    await ready.wait()
    gate = controlled_provider
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://localhost"
    ) as browser:
        response = await browser.post(
            LAUNCH_ENDPOINT, json={"launch": service.create_launch_code()}
        )
        assert response.status_code == 204
        owner = service._request.__self__
        runtime = owner._http_client
        auth_provider.now += 601
        gate.path = "/token"
        request = asyncio.create_task(
            browser.get(SERVICE_PROXY_ENDPOINT + "/conformance")
        )
        await wait_for_http(owner, gate)
        stop.set()
        await asyncio.sleep(0)
        assert not server.done()
        assert not runtime.is_closed
        release_http(gate)
        response = await request
        assert response.status_code == 200
        await asyncio.wait_for(server, 3)
        assert runtime.is_closed
        assert len(auth_provider.grants) == 2
