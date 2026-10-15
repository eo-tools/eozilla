#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

# ruff: noqa: S106

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cuiman import Client
from cuiman.api.auth import (
    TokenAuthConfig,
)
from cuiman.api.config import ClientConfig
from cuiman.app import App, AppBranding, AppEmojiIcon, AppImageIcon
from cuiman.app.launch import (
    CONFIG_ENDPOINT,
    FAVICON_ENDPOINT,
    ICON_ENDPOINT,
    INVALID_LAUNCH_DETAIL,
    INVALID_LAUNCH_STATUS,
    LAUNCH_CODE_TTL_SECONDS,
    LAUNCH_ENDPOINT,
    SERVICE_PROXY_ENDPOINT,
    SESSION_COOKIE_NAME,
    LaunchedAppService,
)


def test_launch_code_is_single_use_and_creates_cookie_session():
    service, client = create_test_client()
    launch_code = service.create_launch_code()

    response = client.post(LAUNCH_ENDPOINT, json={"launch": launch_code})

    assert response.status_code == 204
    assert "HttpOnly" in response.headers["set-cookie"]
    repeated = client.post(LAUNCH_ENDPOINT, json={"launch": launch_code})
    assert repeated.status_code == INVALID_LAUNCH_STATUS
    assert repeated.json() == {"detail": INVALID_LAUNCH_DETAIL}


def test_launch_error_uses_application_display_name():
    class ApplicationConfig(ClientConfig):
        display_name = "Anolis"

    _, client = create_test_client(config_type=ApplicationConfig)
    response = client.post(LAUNCH_ENDPOINT, json={"launch": "expired"})
    assert response.status_code == INVALID_LAUNCH_STATUS
    assert response.json() == {
        "detail": "The Anolis app launch has expired or is no longer valid."
    }
    _, default_client = create_test_client()
    response = default_client.post(LAUNCH_ENDPOINT, json={"launch": "expired"})
    assert response.json() == {"detail": INVALID_LAUNCH_DETAIL}


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

    assert client.post(LAUNCH_ENDPOINT, content=b"not json").status_code == 400
    assert client.post(LAUNCH_ENDPOINT, json={}).status_code == 400
    assert client.post(LAUNCH_ENDPOINT, json={"launch": ""}).status_code == 400
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
        LaunchedAppService(
            App.create_remote_store(),
            ClientConfig(api_url=None),
            prepare=None,
            request=None,
        )


def test_proxy_uses_server_side_headers_and_requires_same_origin(monkeypatch):
    service, client = create_test_client(
        auth=TokenAuthConfig(access_token="secret-token")
    )
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    calls: list[tuple[str, str, dict[str, str]]] = []

    async def send_upstream(request, path):
        calls.append((request.method, path))
        return httpx2.Response(
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
    assert calls == [("POST", "processes")]


def test_proxy_allows_a_same_origin_referer(monkeypatch):
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    async def send_upstream(request, path):
        return httpx2.Response(204)

    monkeypatch.setattr(service, "_send_upstream", send_upstream)

    response = client.delete(
        f"{SERVICE_PROXY_ENDPOINT}/jobs/job-1",
        headers={"Referer": "http://testserver/jobs/job-1"},
    )

    assert response.status_code == 204


def test_proxy_reports_an_unreachable_upstream_as_bad_gateway(monkeypatch):
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    async def send_upstream(request, path):
        raise httpx2.ConnectError(
            "connection refused", request=httpx2.Request("GET", "https://example.test")
        )

    monkeypatch.setattr(service, "_send_upstream", send_upstream)

    response = client.get(SERVICE_PROXY_ENDPOINT)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Unable to reach or authenticate with the processing service."
    }


def test_proxy_rejects_a_path_that_escapes_the_configured_api_base():
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204

    response = client.get(f"{SERVICE_PROXY_ENDPOINT}/%2E%2E/admin")

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Path traversal is not allowed in a proxy request."
    }


def test_proxy_forwards_only_safe_browser_headers_to_the_fixed_upstream(monkeypatch):
    service, client = create_test_client()
    launch_code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": launch_code}).status_code == 204
    received: dict[str, object] = {}

    async def request(method, url, **kwargs):
        received.update(method=method, url=url, **kwargs)
        return httpx2.Response(200, content=b"proxied")

    monkeypatch.setattr(service, "_request", request)

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
        "follow_redirects": False,
        "headers": {
            "accept": "application/json",
            "content-type": "application/json",
        },
    }


def create_test_client(
    auth=None,
    *,
    raise_server_exceptions: bool = True,
    config_type: type[ClientConfig] = ClientConfig,
    branding: AppBranding | None = None,
) -> tuple[LaunchedAppService, TestClient]:
    config = config_type(
        api_url="https://process.example.test/api",
        auth=auth or TokenAuthConfig(access_token="token"),
        branding=branding or AppBranding(),
    )
    owner = Client(config=config)
    service = LaunchedAppService(
        App.create_remote_store(), config, **owner._app_callbacks()
    )
    app = FastAPI()
    service._init_app(app)
    return service, TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.mark.parametrize(
    "branding, expected",
    [
        (None, {}),
        (AppBranding(), {}),
        (AppBranding(title="Sen4CAP"), {"title": "Sen4CAP"}),
        (
            AppBranding(
                title="Sen4CAP",
                favicon="./favicon.svg",
                icon=AppEmojiIcon(emoji="🌍"),
            ),
            {"title": "Sen4CAP", "favicon": "./favicon.svg", "icon": {"emoji": "🌍"}},
        ),
        (
            AppBranding(icon=AppImageIcon(url="https://example.test/logo.png")),
            {"icon": {"url": "https://example.test/logo.png"}},
        ),
        (
            AppBranding(icon=AppImageIcon(url="./logo.svg")),
            {"icon": {"url": "./logo.svg"}},
        ),
    ],
)
def test_config_requires_a_session_and_survives_reload(branding, expected):
    service, client = create_test_client(branding=branding)
    response = client.get(CONFIG_ENDPOINT)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    client.cookies.set(SESSION_COOKIE_NAME, "invalid")
    assert client.get(CONFIG_ENDPOINT).status_code == 401
    client.cookies.clear()
    code = service.create_launch_code()
    response = client.post(LAUNCH_ENDPOINT, json={"launch": code})
    assert response.status_code == 204
    assert response.content == b""
    for _ in range(2):
        response = client.get(CONFIG_ENDPOINT)
        assert response.status_code == 200
        assert response.json() == {"branding": expected}
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "application/json"
    assert client.post(LAUNCH_ENDPOINT, json={"launch": code}).status_code == 410
    assert client.get(CONFIG_ENDPOINT).json() == {"branding": expected}


def test_branding_is_snapshotted_and_not_shared_between_app_servers():
    branding = AppBranding(title="Original", icon=AppImageIcon(url="./original.svg"))
    first, first_client = create_test_client(branding=branding)
    second, second_client = create_test_client(branding=AppBranding(title="Second"))
    branding.title = "Changed"
    branding.icon.url = "./changed.svg"
    for service, client in [(first, first_client), (second, second_client)]:
        code = service.create_launch_code()
        assert client.post(LAUNCH_ENDPOINT, json={"launch": code}).status_code == 204
    assert first_client.get(CONFIG_ENDPOINT).json() == {
        "branding": {"title": "Original", "icon": {"url": "./original.svg"}}
    }
    assert second_client.get(CONFIG_ENDPOINT).json() == {
        "branding": {"title": "Second"}
    }
    # A cookie from another app server cannot authorize configuration access.
    second_client.cookies.clear()
    second_client.cookies.update(first_client.cookies)
    assert second_client.get(CONFIG_ENDPOINT).status_code == 401


def test_config_works_below_a_jupyter_proxy_prefix():
    service, _ = create_test_client(
        branding=AppBranding(
            favicon="./favicon.svg", icon=AppImageIcon(url="./logo.svg")
        )
    )
    app = FastAPI()
    service._init_app(app)
    prefix = "/user/norman/proxy/8765"
    client = TestClient(app, root_path=prefix, base_url=f"http://testserver{prefix}/")
    response = client.get("config.json")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    code = service.create_launch_code()
    assert client.post("_cuiman/launch", json={"launch": code}).status_code == 204
    response = client.get("config.json")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "branding": {"favicon": "./favicon.svg", "icon": {"url": "./logo.svg"}}
    }


@pytest.mark.parametrize(
    "filename, media_type",
    [
        ("image.svg", "image/svg+xml"),
        ("image.png", "image/png"),
        ("image.unknown-branding-type", "application/octet-stream"),
    ],
)
def test_local_assets_are_authenticated_snapshots_below_a_proxy_prefix(
    tmp_path, filename, media_type
):
    image = tmp_path / filename
    image.write_bytes(b"original image")
    branding = AppBranding(icon=AppImageIcon(path=image))
    # Path shorthand also works when assigned after construction.
    branding.favicon = image
    service, _ = create_test_client(branding=branding)
    app = FastAPI()
    service._init_app(app)
    prefix = "/user/norman/proxy/8765"
    client = TestClient(app, root_path=prefix, base_url=f"http://testserver{prefix}/")
    for endpoint in (FAVICON_ENDPOINT, ICON_ENDPOINT):
        response = client.get(f".{endpoint}")
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    code = service.create_launch_code()
    assert client.post("_cuiman/launch", json={"launch": code}).status_code == 204
    assert client.get("config.json").json() == {
        "branding": {
            "favicon": f".{FAVICON_ENDPOINT}",
            "icon": {"url": f".{ICON_ENDPOINT}"},
        }
    }
    image.unlink()
    for endpoint in (FAVICON_ENDPOINT, ICON_ENDPOINT):
        response = client.get(f".{endpoint}")
        assert response.status_code == 200
        assert response.content == b"original image"
        assert response.headers["content-type"] == media_type
        assert response.headers["cache-control"] == "no-store"
    assert client.get("_cuiman/assets/other").status_code == 404
    assert client.get("_cuiman/assets/%2E%2E/private").status_code == 404
    # A different server cannot use this server's image snapshot or session.
    _, other = create_test_client()
    other.cookies.update(client.cookies)
    assert other.get(ICON_ENDPOINT).status_code == 401


def test_missing_local_assets_warn_and_use_defaults(tmp_path):
    image = tmp_path / "missing.svg"
    with pytest.warns(UserWarning, match="Branding image file not found") as warnings:
        service, client = create_test_client(
            branding=AppBranding(
                title="Custom", favicon=image, icon=AppImageIcon(path=image)
            )
        )
    assert len(warnings) == 2
    code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": code}).status_code == 204
    assert client.get(CONFIG_ENDPOINT).json() == {"branding": {"title": "Custom"}}
    for endpoint in (FAVICON_ENDPOINT, ICON_ENDPOINT):
        response = client.get(endpoint)
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"


def test_browser_urls_are_passed_through_without_local_asset_endpoints():
    service, client = create_test_client(
        branding=AppBranding(
            favicon=AppImageIcon(url="https://example.test/favicon.ico"),
            icon=AppImageIcon(url="./logo.svg"),
        )
    )
    code = service.create_launch_code()
    assert client.post(LAUNCH_ENDPOINT, json={"launch": code}).status_code == 204
    assert client.get(CONFIG_ENDPOINT).json() == {
        "branding": {
            "favicon": "https://example.test/favicon.ico",
            "icon": {"url": "./logo.svg"},
        }
    }
    assert client.get(FAVICON_ENDPOINT).status_code == 404
    assert client.get(ICON_ENDPOINT).status_code == 404


def test_local_assets_expand_home_and_propagate_read_errors(tmp_path, monkeypatch):
    image = tmp_path / "logo.svg"
    image.write_bytes(b"home image")
    monkeypatch.setattr("pathlib.Path.expanduser", lambda self: image)
    service, client = create_test_client(
        branding=AppBranding(favicon=AppImageIcon(path="~/logo.svg"))
    )
    code = service.create_launch_code()
    client.post(LAUNCH_ENDPOINT, json={"launch": code})
    assert client.get(FAVICON_ENDPOINT).content == b"home image"

    def denied(self):
        raise PermissionError("Cannot read image")

    monkeypatch.setattr("pathlib.Path.read_bytes", denied)
    with pytest.raises(PermissionError, match="Cannot read image"):
        create_test_client(branding=AppBranding(favicon=image))
