#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

# ruff: noqa: S106

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuiman.api.auth import LoginAuthConfig, TokenAuthConfig
from cuiman.api.config import ClientConfig
from cuiman.app import App
from cuiman.app.launch import (
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


def create_test_client(auth=None) -> tuple[LaunchedAppService, TestClient]:
    config = ClientConfig(
        api_url="https://process.example.test/api",
        auth=auth or TokenAuthConfig(access_token="token"),
    )
    service = LaunchedAppService(App.create_remote_store(), config)
    app = FastAPI()
    service._init_app(app)
    return service, TestClient(app)
