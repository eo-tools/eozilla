#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import importlib
import webbrowser

import pytest
from IPython import display as ipython_display

from cuiman.api.config import ClientConfig
from cuiman.app.store import create_app_remote_store

serve_module = importlib.import_module("cuiman.app.serve")


def test_find_free_port_returns_available_port():
    port = serve_module._find_free_port()

    assert isinstance(port, int)
    assert 0 < port < 65536


@pytest.mark.parametrize(
    "value, expected",
    [
        ("http://example.test/app", True),
        ("https://example.test/app", True),
        ("ftp://example.test/app", False),
        ("C:/dist", False),
        (None, False),
        (42, False),
    ],
)
def test_is_url_str(value, expected):
    assert serve_module._is_url_str(value) is expected


def test_get_app_dist_url_or_dir_uses_default_dist(monkeypatch):
    monkeypatch.setattr(serve_module, "files", lambda package: FakeFiles(package))
    monkeypatch.setattr(serve_module, "StaticFiles", FakeStaticFiles)

    dist_url, dist_dir = serve_module._get_app_dist_url_or_dir(
        None,
        server_host="127.0.0.1",
        server_port=1234,
    )

    assert dist_url == "http://127.0.0.1:1234"
    assert isinstance(dist_dir, FakeStaticFiles)
    assert dist_dir.directory == "fake/cuiman.app/dist"
    assert dist_dir.html is True


def test_get_app_dist_url_or_dir_accepts_explicit_dist_dir(monkeypatch):
    monkeypatch.setattr(serve_module, "StaticFiles", FakeStaticFiles)

    dist_url, dist_dir = serve_module._get_app_dist_url_or_dir(
        "C:/app/dist",
        server_host="localhost",
        server_port=1234,
    )

    assert dist_url == "http://localhost:1234"
    assert isinstance(dist_dir, FakeStaticFiles)
    assert dist_dir.directory == "C:/app/dist"
    assert dist_dir.html is True


def test_get_app_dist_url_or_dir_accepts_explicit_dist_url():
    dist_url, dist_dir = serve_module._get_app_dist_url_or_dir(
        "https://cdn.example.test/app",
        server_host="localhost",
        server_port=1234,
    )

    assert dist_url == "https://cdn.example.test/app"
    assert dist_dir is None


def test_get_app_dist_url_or_dir_falls_back_when_host_and_port_are_none(monkeypatch):
    monkeypatch.setattr(serve_module, "_find_free_port", lambda: 5555)

    dist_url, dist_dir = serve_module._get_app_dist_url_or_dir(
        "https://cdn.example.test/app",
        server_host=None,
        server_port=None,
    )

    assert dist_url == "https://cdn.example.test/app"
    assert dist_dir is None


def test_serve_opens_browser(monkeypatch):
    calls = install_serve_fakes(monkeypatch)
    monkeypatch.setattr(webbrowser, "open", calls["browser_open"].append)

    serve_module.serve(
        ClientConfig(api_url="https://api.example.test"),
        create_app_remote_store(),
        compact=False,
        scheme="light",
        open_in_browser=True,
        open_in_notebook=True,
    )

    assert calls["served"] == [
        {
            "service": "service-wrapper",
            "ui_dist": None,
            "host": "127.0.0.1",
            "port": 8765,
            "open_browser": False,
            "open_iframe": False,
        }
    ]
    assert calls["url"][0]["base_url"] == "https://app.example.test"
    assert calls["url"][0]["ws_url"] == "ws://127.0.0.1:8765/ws"
    assert calls["url"][0]["compact"] is False
    assert calls["url"][0]["scheme"] == "light"
    assert calls["url"][0]["service"].options["apiUrl"] == "https://api.example.test/"
    assert calls["browser_open"] == ["https://app.example.test/index.html"]
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
        create_app_remote_store(),
        scheme="auto",
        width="80%",
        height=500,
        open_in_browser=False,
        open_in_notebook=True,
    )

    assert calls["display"] == [
        {
            "app_url": "https://app.example.test/index.html",
            "auto_scheme": True,
            "width": "80%",
            "height": 500,
        }
    ]


class FakeFiles:
    def __init__(self, package):
        self.package = package

    def joinpath(self, path):
        return FakePath(f"fake/{self.package}/{path}")


class FakePath:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class FakeStaticFiles:
    def __init__(self, *, directory, html):
        self.directory = directory
        self.html = html


def install_serve_fakes(monkeypatch):
    calls = {
        "browser_open": [],
        "display": [],
        "served": [],
        "url": [],
    }

    monkeypatch.setenv(serve_module.DIST_ENV_VAR, "https://app.example.test")
    monkeypatch.setattr(serve_module, "_find_free_port", lambda: 8765)
    monkeypatch.setattr(serve_module.rs, "Service", lambda store: "service-wrapper")

    def fake_serve(service, **kwargs):
        calls["served"].append({"service": service, **kwargs})

    def fake_create_app_url(base_url, ws_url, *, compact, scheme, service):
        calls["url"].append(
            {
                "base_url": base_url,
                "ws_url": ws_url,
                "compact": compact,
                "scheme": scheme,
                "service": service,
            }
        )
        return "https://app.example.test/index.html"

    monkeypatch.setattr(serve_module.rs, "serve", fake_serve)
    monkeypatch.setattr(serve_module, "create_app_url", fake_create_app_url)
    return calls
