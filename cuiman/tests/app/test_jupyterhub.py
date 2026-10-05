"""Exercise Hub authentication through real app routes and client lifecycles."""

import asyncio
import importlib
import inspect
import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import JupyterHubAuth
from cuiman.app import App
from cuiman.app.launch import LAUNCH_ENDPOINT, SERVICE_PROXY_ENDPOINT


async def invoke(method, *args, **kwargs):
    result = method(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def kind(request):
    return request.param


@pytest.fixture
def launch(monkeypatch):
    """Run the actual app service and lifespan without opening a listening port."""
    module = importlib.import_module("cuiman.app.serve")
    captured = {}

    def start(service, **kwargs):
        captured.update(service=service, **kwargs)
        return Mock()

    monkeypatch.setattr(module.rs, "serve", start)

    def create(owner=None, config=None):
        module.serve(
            owner.config if owner else config,
            App.create_remote_store(),
            client=owner,
            display="none",
        )
        return captured["service"], captured["app"]

    return create


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_type", ["auto", "jupyter", "adapter"])
async def test_python_and_app_use_current_hub_token_on_same_session(
    kind, hub, hub_environment, launch, auth_type
):
    auth = (
        JupyterHubAuth(hub_api_url=hub.api_url, hub_api_token=hub.api_token)
        if auth_type == "adapter"
        else {"auth_type": auth_type}
    )
    owner = kind(api_url="https://processing.test/api", auth=auth)
    try:
        await invoke(owner.get_conformance)
        runtime = owner._http_client
        service, app = launch(owner)

        def browse():
            with TestClient(app) as browser:
                code = service.create_launch_code()
                response = browser.post(LAUNCH_ENDPOINT, json={"launch": code})
                assert response.status_code == 204
                assert "HttpOnly" in response.headers["set-cookie"]
                hub.body = {"auth_state": {"access_token": "upstream-new"}}
                response = browser.get(
                    SERVICE_PROXY_ENDPOINT + "/conformance",
                    headers={"Authorization": "Bearer browser-token"},
                )
                assert response.status_code == 200
                public = response.text + str(response.headers) + str(browser.cookies)
                assert hub.api_token not in public
                assert "upstream-new" not in public
                assert (
                    hub.requests[-1].headers["authorization"] == "Bearer upstream-new"
                )
                assert "cookie" not in hub.requests[-2].headers
                assert "cookie" not in hub.requests[-1].headers

        await asyncio.to_thread(browse)
        assert owner._http_client is runtime
        assert not runtime.is_closed
        hub.body = {"auth_state": {"access_token": "upstream-latest"}}
        await invoke(owner.get_conformance)
        assert hub.requests[-1].headers["authorization"] == "Bearer upstream-latest"
        assert len(hub.clients) == 1
        assert [r.url.host for r in hub.requests] == [
            "hub.test",
            "processing.test",
            "hub.test",
            "hub.test",
            "processing.test",
            "hub.test",
            "processing.test",
        ]
        assert owner.token is None
        assert "upstream-" not in json.dumps(owner.config.to_file_dict())
    finally:
        await invoke(owner.logout)
    assert runtime.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_type", ["auto", "jupyter"])
@pytest.mark.parametrize("failure", ["http", "auth-state"])
async def test_failed_launch_and_proxy_never_send_processing_or_leak_tokens(
    kind, hub, hub_environment, launch, auth_type, failure
):
    owner = kind(api_url="https://processing.test", auth={"auth_type": auth_type})
    service, app = launch(owner)
    hub.status = 403 if failure == "http" else 200
    hub.body = {"private": "provider-secret"}

    def browse():
        with TestClient(app) as browser:
            code = service.create_launch_code()
            response = browser.post(LAUNCH_ENDPOINT, json={"launch": code})
            assert response.status_code == 502
            assert "provider-secret" not in response.text
            assert hub.api_token not in str(response.headers)
            assert "set-cookie" not in response.headers
            assert code in service._launch_codes
            assert not service._sessions
            assert [r.url.host for r in hub.requests] == ["hub.test"]

            hub.status = 200
            hub.body = {"auth_state": {"access_token": "upstream-recovered"}}
            assert (
                browser.post(LAUNCH_ENDPOINT, json={"launch": code}).status_code == 204
            )
            hub.body = {"auth_state": None, "private": "provider-secret"}
            endpoint = SERVICE_PROXY_ENDPOINT + "/processes/p/execution"
            options = {
                "json": {"inputs": {}},
                "headers": {"Origin": "http://testserver"},
            }
            response = browser.post(endpoint, **options)
            assert response.status_code == 502
            assert "provider-secret" not in response.text
            assert all(r.url.host == "hub.test" for r in hub.requests)

            hub.body = {"auth_state": {"access_token": "upstream-recovered"}}
            hub.processing_status = 401
            assert browser.post(endpoint, **options).status_code == 401
            processing = [r for r in hub.requests if r.url.host == "processing.test"]
            assert len(processing) == 1
            assert processing[0].method == "POST"
            assert json.loads(processing[0].content) == {"inputs": {}}

    try:
        await asyncio.to_thread(browse)
    finally:
        await invoke(owner.close)
    assert all(client.is_closed for client in hub.clients)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["close", "logout"])
async def test_closed_hub_owner_cannot_be_replaced_by_app(
    kind, hub, hub_environment, launch, operation
):
    owner = kind(api_url="https://processing.test")
    service, app = launch(owner)
    await invoke(owner.login, interactive=False)
    runtime = owner._http_client
    try:
        with TestClient(app) as browser:
            code = service.create_launch_code()
            response = await asyncio.to_thread(
                browser.post, LAUNCH_ENDPOINT, json={"launch": code}
            )
            assert response.status_code == 204
            await invoke(getattr(owner, operation))
            request_count = len(hub.requests)
            response = await asyncio.to_thread(
                browser.get, SERVICE_PROXY_ENDPOINT + "/conformance"
            )
            assert response.status_code == 502
            assert len(hub.requests) == request_count
            assert len(hub.clients) == 1
            assert runtime.is_closed
    finally:
        await invoke(owner.close)


@pytest.mark.parametrize("auth_type", ["auto", "jupyter"])
def test_standalone_app_owns_and_closes_hub_session(
    hub, hub_environment, launch, auth_type
):
    service, app = launch(
        config=ClientConfig(
            api_url="https://processing.test", auth={"auth_type": auth_type}
        )
    )
    with TestClient(app) as browser:
        response = browser.post(
            LAUNCH_ENDPOINT, json={"launch": service.create_launch_code()}
        )
        assert response.status_code == 204
        assert browser.get(SERVICE_PROXY_ENDPOINT + "/conformance").status_code == 200
        assert len(hub.clients) == 1
        assert not hub.clients[0].is_closed
    assert hub.clients[0].is_closed
    assert [r.url.host for r in hub.requests] == [
        "hub.test",
        "hub.test",
        "processing.test",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_type", ["auto", "jupyter"])
async def test_logout_before_discovery_needs_neither_hub_nor_keyring(
    kind, hub, auth_type
):
    owner = kind(api_url="https://processing.test", auth={"auth_type": auth_type})
    await invoke(owner.logout)
    assert not hub.requests and not hub.clients
    with pytest.raises(RuntimeError, match="closed"):
        await invoke(owner.get_conformance)
