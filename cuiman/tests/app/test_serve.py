#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import importlib
import webbrowser
from dataclasses import dataclass

from IPython import display as ipython_display

from cuiman.api.config import ClientConfig
from cuiman.app.state import AppState

serve_module = importlib.import_module("cuiman.app.serve")


def test_get_app_dist_url_or_dir_uses_default_dist(monkeypatch):
    monkeypatch.setattr(serve_module, "files", lambda package: FakeFiles(package))

    dist = serve_module._get_app_dist_url_or_dir(None)

    assert dist == "fake/cuiman.app/dist"


def test_get_app_dist_url_or_dir_accepts_explicit_dist_url_or_dir():
    assert (
        serve_module._get_app_dist_url_or_dir("https://cdn.example.test/app")
        == "https://cdn.example.test/app"
    )
    assert serve_module._get_app_dist_url_or_dir("C:/app/dist") == "C:/app/dist"


def test_serve_returns_server_without_display(monkeypatch):
    calls = install_serve_fakes(monkeypatch)

    server = serve_module.serve(
        ClientConfig(api_url="https://api.example.test"),
        AppState().store,
        display="none",
    )

    assert server is calls["server"]
    assert calls["served"] == [
        {
            "service": "service-wrapper",
            "ui_dist": "https://app.example.test",
            "host": "127.0.0.1",
            "display": "none",
        }
    ]
    assert calls["url"] == []
    assert calls["browser_open"] == []
    assert calls["display"] == []


def test_serve_opens_browser(monkeypatch):
    calls = install_serve_fakes(monkeypatch)

    serve_module.serve(
        ClientConfig(api_url="https://api.example.test"),
        AppState().store,
        compact=False,
        debug=True,
        scheme="light",
        display="browser",
    )

    assert calls["served"] == [
        {
            "service": "service-wrapper",
            "ui_dist": "https://app.example.test",
            "host": "127.0.0.1",
            "display": "none",
        }
    ]
    assert calls["url"][0]["base_url"] == "http://127.0.0.1:8765"
    assert calls["url"][0]["ws_url"] == "ws://127.0.0.1:8765/ws"
    assert calls["url"][0]["compact"] is False
    assert calls["url"][0]["debug"] is True
    assert calls["url"][0]["scheme"] == "light"
    assert calls["url"][0]["service"].options["apiUrl"] == "https://api.example.test/"
    assert calls["browser_open"] == ["http://127.0.0.1:8765/index.html"]
    assert calls["display"] == []


def test_serve_displays_in_notebook(monkeypatch):
    calls = install_serve_fakes(monkeypatch)
    monkeypatch.setattr(ipython_display, "display", calls["display"].append)
    monkeypatch.setattr(
        serve_module,
        "create_app_display_object",
        lambda app_url, auto_scheme, width, height: {
            "app_url": app_url,
            "auto_scheme": auto_scheme,
            "width": width,
            "height": height,
        },
    )

    serve_module.serve(
        ClientConfig(api_url="https://api.example.test"),
        AppState().store,
        scheme="auto",
        width="80%",
        height=500,
        display="notebook",
    )

    assert calls["display"] == [
        {
            "app_url": "http://127.0.0.1:8765/index.html",
            "auto_scheme": True,
            "width": "80%",
            "height": 500,
        }
    ]
    assert calls["browser_open"] == []


class FakeFiles:
    def __init__(self, package):
        self.package = package

    # noinspection SpellCheckingInspection
    def joinpath(self, path):
        return FakePath(f"fake/{self.package}/{path}")


class FakePath:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


@dataclass
class FakeServeResult:
    ui_base_url: str = "http://127.0.0.1:8765"
    ws_url: str = "ws://127.0.0.1:8765/ws"


def install_serve_fakes(monkeypatch):
    calls = {
        "browser_open": [],
        "display": [],
        "served": [],
        "url": [],
        "server": FakeServeResult(),
    }

    monkeypatch.setenv(serve_module.DIST_ENV_VAR, "https://app.example.test")
    monkeypatch.setattr(serve_module.rs, "Service", lambda store: "service-wrapper")

    def fake_serve(service, **kwargs):
        calls["served"].append({"service": service, **kwargs})
        return calls["server"]

    def fake_create_app_url(base_url, ws_url, *, compact, debug, scheme, service):
        calls["url"].append(
            {
                "base_url": base_url,
                "ws_url": ws_url,
                "compact": compact,
                "debug": debug,
                "scheme": scheme,
                "service": service,
            }
        )
        return f"{base_url}/index.html"

    monkeypatch.setattr(serve_module.rs, "serve", fake_serve)
    monkeypatch.setattr(serve_module, "create_app_url", fake_create_app_url)
    monkeypatch.setattr(webbrowser, "open", calls["browser_open"].append)
    return calls
