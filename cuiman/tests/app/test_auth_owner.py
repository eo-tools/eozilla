"""The app borrows its Python owner's requester, including token updates."""

import asyncio
import importlib
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.app import App
from cuiman.app.launch import (
    LAUNCH_ENDPOINT,
    SERVICE_PROXY_ENDPOINT,
    LaunchedAppService,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [Client, AsyncClient])
async def test_api_and_proxy_share_the_live_client(kind, auth_provider):
    owner = kind(
        api_url="https://processing.test",
        auth=dict(
            auth_type="oauth2",
            token_url="https://identity.test/token",
            client_id="client",
            username="user",
            password="secret",
        ),
    )
    if kind is AsyncClient:
        await owner.get_conformance()
    else:
        owner.get_conformance()
    runtime = owner._http_client
    service = LaunchedAppService(
        App.create_remote_store(), owner.config, **owner._app_callbacks()
    )
    app = FastAPI()
    service._init_app(app)

    def browse():
        with TestClient(app) as browser:
            for _ in range(2):
                response = browser.post(
                    LAUNCH_ENDPOINT, json={"launch": service.create_launch_code()}
                )
                assert response.status_code == 204
            auth_provider.now += 601
            response = browser.get(
                SERVICE_PROXY_ENDPOINT + "/conformance",
                headers={"Authorization": "Bearer browser-token"},
            )
            assert response.status_code == 200
            assert "access-" not in response.text
            auth_provider.statuses.append(401)
            assert (
                browser.get(SERVICE_PROXY_ENDPOINT + "/conformance").status_code == 401
            )
        assert service._sessions and all(isinstance(s, str) for s in service._sessions)

    await asyncio.to_thread(browse)
    assert owner._http_client is runtime
    assert len(auth_provider.grants) == 2
    assert auth_provider.requests[-1].headers["Authorization"] == "Bearer access-2"
    assert not runtime.is_closed
    if kind is AsyncClient:
        await owner.close()
    else:
        owner.close()


@pytest.mark.asyncio
async def test_async_owner_rejects_another_event_loop_and_closed_proxy_use(
    auth_provider,
):
    owner = AsyncClient(api_url="https://processing.test")
    callbacks = owner._app_callbacks()
    await callbacks["prepare"]()
    with pytest.raises(RuntimeError, match="owning event loop"):
        await asyncio.to_thread(lambda: asyncio.run(owner.login()))
    await owner.close()
    with pytest.raises(RuntimeError, match="closed"):
        await callbacks["request"]("GET", "https://processing.test")


def test_proxy_detects_stopped_async_owner_without_hanging():
    owner = AsyncClient(api_url="https://processing.test")

    async def capture():
        return owner._app_callbacks()

    callbacks = asyncio.run(capture())
    with pytest.raises(RuntimeError, match="not running"):
        asyncio.run(callbacks["prepare"]())


def test_failed_prepare_preserves_launch_code_and_hides_provider_errors():
    async def prepare():
        raise ValueError("sensitive provider details")

    service = LaunchedAppService(
        App.create_remote_store(),
        ClientConfig(api_url="https://processing.test"),
        prepare=prepare,
        request=Mock(),
    )
    app = FastAPI()
    service._init_app(app)
    code = service.create_launch_code()
    with TestClient(app) as browser:
        response = browser.post(LAUNCH_ENDPOINT, json={"launch": code})
        assert response.status_code == 502
        assert "sensitive" not in response.text
        assert code in service._launch_codes


@pytest.mark.parametrize("borrow", [False, True])
def test_server_lifespan_closes_only_owned_client(borrow, auth_provider, monkeypatch):
    serve = importlib.import_module("cuiman.app.serve")
    captured = {}

    def start(service, **kwargs):
        captured.update(service=service, **kwargs)
        return Mock()

    monkeypatch.setattr(serve.rs, "serve", start)
    config = ClientConfig(api_url="https://processing.test")
    owner = Client(config=config) if borrow else None
    serve.serve(config, App.create_remote_store(), client=owner, display="none")
    service = captured["service"]
    with TestClient(captured["app"]) as browser:
        response = browser.post(
            LAUNCH_ENDPOINT, json={"launch": service.create_launch_code()}
        )
        assert response.status_code == 204
        assert browser.get(SERVICE_PROXY_ENDPOINT + "/conformance").status_code == 200
        if not borrow:
            owner = service._request.__self__
        runtime = owner._http_client
    assert runtime.is_closed is (not borrow)
    if borrow:
        owner.close()
