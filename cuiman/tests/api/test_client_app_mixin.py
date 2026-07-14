#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

import cuiman.app as app_package
import cuiman.app.app as app_module
import cuiman.api.client_app_mixin as client_app_mixin
from cuiman.api.client_app_mixin import ClientAppMixin
from cuiman.api.config import ClientConfig
from cuiman.app import App


def test_show_app_uses_notebook_display_and_explicit_compact(monkeypatch):
    calls = []
    serve_result = object()

    monkeypatch.setattr(client_app_mixin, "has_ishell", True)
    monkeypatch.setattr(app_module, "ensure_type", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        app_package,
        "serve",
        lambda *args, **kwargs: calls.append((args, kwargs)) or serve_result,
    )

    client = FakeAppClient()

    app = client.show_app(compact=False, debug=True, scheme="dark", width="80%", height=400)

    assert len(calls) == 1
    assert calls[0][0][0] == client.config
    assert calls[0][1] == {
        "compact": False,
        "debug": True,
        "scheme": "dark",
        "width": "80%",
        "height": 400,
        "display": "notebook",
    }
    assert isinstance(app, App)
    assert app.serve_result is serve_result
    assert app.remote_store.get("processRequests") == {}


def test_show_app_uses_browser_display_when_no_shell(monkeypatch):
    calls = []
    serve_result = object()

    monkeypatch.setattr(client_app_mixin, "has_ishell", False)
    monkeypatch.setattr(app_module, "ensure_type", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        app_package,
        "serve",
        lambda *args, **kwargs: calls.append((args, kwargs)) or serve_result,
    )

    client = FakeAppClient()

    app = client.show_app()

    assert len(calls) == 1
    assert calls[0][0][0] == client.config
    assert calls[0][1] == {
        "compact": False,
        "debug": False,
        "scheme": "auto",
        "width": "100%",
        "height": 600,
        "display": "browser",
    }
    assert isinstance(app, App)
    assert app.serve_result is serve_result


class FakeAppClient(ClientAppMixin):
    def __init__(self):
        self._config = ClientConfig(api_url="https://api.example.test")

    @property
    def config(self) -> ClientConfig:
        return self._config
