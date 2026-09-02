#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

# ruff: noqa: S106

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuiman.api.auth import (
    LoginAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
    TokenResult,
)
from cuiman.api.config import ClientConfig
from cuiman.app import App
from cuiman.app.launch import (
    LAUNCH_CODE_TTL_SECONDS,
    LAUNCH_ENDPOINT,
    SERVICE_PROXY_ENDPOINT,
    LaunchedAppService,
)


def test_launch_code_is_single_use_and_creates_cookie_session():
    service, client = create_test_client()
    launch_code = service.create_launch_code()

    response = client.post(LAUNCH_ENDPOINT, json={"launch": launch_code})

    assert response.status_code == 204
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 401


def test_launch_session_cookie_is_secure_behind_an_https_proxy():
    service, client = create_test_client()
    launch_code = service.create_launch_code()

    response = client.post(
        LAUNCH_ENDPOINT,
        json={"launch": launch_code},
        headers={"X-Forwarded-Proto": "https"},
    )

    assert "Secure" in response.headers["set-cookie"]


def test_launch_rejects_invalid_payloads_and_proxy_requests_without_a_session():
    _, client = create_test_client()

    assert (
        client.post(LAUNCH_ENDPOINT, content=b"not json").status_code == 401
    )
    assert client.post(LAUNCH_ENDPOINT, json={}).status_code == 401
    assert client.post(LAUNCH_ENDPOINT, json={"launch": ""}).status_code == 401
    assert client.get(SERVICE_PROXY_ENDPOINT).status_code == 401


def test_launch_code_expiry_and_missing_api_url_are_rejected(monkeypatch):
    service, _ = create_test_client()
    launch_code = service.create_launch_code()
    created_at = service._launch_codes[launch_code].created_at
    monkeypatch.setattr(
        "cuiman.app.launch.time.monotonic",
        lambda: created_at + LAUNCH_CODE_TTL_SECONDS + 1,
    )

    service._remove_expired_launch_codes()

    assert launch_code not in service._launch_codes
    with pytest.raises(ValueError, match="api_url"):
        LaunchedAppService(App.create_remote_store(), ClientConfig(api_url=None))


def test_proxy_uses_server_side_headers_and_requires_same_origin(monkeypatch):
    service, client = create_test_client(
        auth=TokenAuthConfig(access_token="secret-token")
    )
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    calls: list[tuple[str, str, dict[str, str]]] = []

    async def send_upstream(request, path, auth_headers):
        calls.append((request.method, path, auth_headers))
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"Set-Cookie": "must-not-reach-browser", "X-Upstream": "yes"},
        )

    monkeypatch.setattr(service, "_send_upstream", send_upstream)

    assert client.post(f"{SERVICE_PROXY_ENDPOINT}/processes").status_code == 403
    response = client.post(
        f"{SERVICE_PROXY_ENDPOINT}/processes",
        headers={"Origin": "http://testserver"},
    )

    assert response.json() == {"ok": True}
    assert response.headers["x-upstream"] == "yes"
    assert "set-cookie" not in response.headers
    assert calls == [
        ("POST", "processes", {"Authorization": "Bearer secret-token"})
    ]


def test_proxy_allows_a_same_origin_referer(monkeypatch):
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    async def send_upstream(request, path, auth_headers):
        return httpx.Response(204)

    monkeypatch.setattr(service, "_send_upstream", send_upstream)

    response = client.delete(
        f"{SERVICE_PROXY_ENDPOINT}/jobs/job-1",
        headers={"Referer": "http://testserver/jobs/job-1"},
    )

    assert response.status_code == 204


def test_proxy_forwards_only_safe_browser_headers_to_the_fixed_upstream(monkeypatch):
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204
    received: dict[str, object] = {}

    class StubAsyncClient:
        def __init__(self, *, follow_redirects):
            assert follow_redirects is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def request(self, method, url, **kwargs):
            received.update(method=method, url=url, **kwargs)
            return httpx.Response(200, content=b"proxied")

    monkeypatch.setattr("cuiman.app.launch.httpx.AsyncClient", StubAsyncClient)

    response = client.get(
        f"{SERVICE_PROXY_ENDPOINT}/jobs/a%20job?tag=one&tag=two",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer browser-token",
        },
    )

    assert response.content == b"proxied"
    assert received == {
        "method": "GET",
        "url": "https://process.example.test/api/jobs/a%20job",
        "params": [("tag", "one"), ("tag", "two")],
        "content": b"",
        "headers": {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": "Bearer token",
        },
    }


def test_launch_resolves_login_credentials_on_the_server(monkeypatch):
    service, client = create_test_client(
        auth=LoginAuthConfig(
            login_url="https://auth.example.test/login",
            username="user",
            password="password",
        )
    )

    async def login(_auth):
        return "resolved-token"

    monkeypatch.setattr("cuiman.app.launch.login_async", login)
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    session = next(iter(service._sessions.values()))
    assert session.headers == {"Authorization": "Bearer resolved-token"}


def test_launch_resolves_oauth2_credentials_on_the_server(monkeypatch):
    service, client = create_test_client(
        auth=OAuth2AuthConfig(
            token_url="https://auth.example.test/token",
            username="user",
            password="password",
        )
    )

    tokens = TokenResult(
        access_token="resolved-token", refresh_token="refresh-token"
    )

    async def obtain_tokens(_auth):
        return tokens

    monkeypatch.setattr("cuiman.app.launch.obtain_oauth2_tokens_async", obtain_tokens)
    launch_code = service.create_launch_code()

    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204
    assert service._client_config.auth.access_token == tokens.access_token
    assert service._client_config.auth.refresh_token == tokens.refresh_token


def test_proxy_refreshes_credentials_once_after_an_upstream_unauthorized_response(
    monkeypatch,
):
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204
    calls: list[dict[str, str]] = []

    async def send_upstream(request, path, auth_headers):
        calls.append(auth_headers)
        return httpx.Response(401 if len(calls) == 1 else 200)

    async def refresh():
        return {"Authorization": "Bearer refreshed-token"}

    monkeypatch.setattr(service, "_send_upstream", send_upstream)
    monkeypatch.setattr(
        ClientConfig,
        "_make_async_token_refresher",
        lambda _config: refresh,
    )

    assert client.get(f"{SERVICE_PROXY_ENDPOINT}/processes").status_code == 200
    assert calls == [
        {"Authorization": "Bearer token"},
        {"Authorization": "Bearer refreshed-token"},
    ]


def create_test_client(auth=None) -> tuple[LaunchedAppService, TestClient]:
    config = ClientConfig(
        api_url="https://process.example.test/api",
        auth=auth or TokenAuthConfig(access_token="token"),
    )
    service = LaunchedAppService(App.create_remote_store(), config)
    app = FastAPI()
    service._init_app(app)
    return service, TestClient(app)
