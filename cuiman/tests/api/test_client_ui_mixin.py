#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.


import cuiman.app as app
from cuiman.api import client_app_mixin
from cuiman.api.client_app_mixin import ClientAppMixin
from cuiman.api.config import ClientConfig
from cuiman.app import AppState


def test_app_store_is_created_and_cached():
    client = FakeAppClient()

    assert isinstance(client.app_state, AppState)
    assert client.app_state is client.app_state


def test_show_app_serves_notebook_display_in_interactive_shell(monkeypatch):
    calls = []
    store = object()
    monkeypatch.setattr(client_app_mixin, "has_ishell", True)
    monkeypatch.setattr(app, "AppState", lambda: store)
    monkeypatch.setattr(
        app, "serve", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    client = FakeAppClient()
    client.show_app(debug=True, scheme="dark", width="80%", height=400)

    assert calls == [
        (
            (client.config, store),
            {
                "compact": True,
                "debug": True,
                "scheme": "dark",
                "width": "80%",
                "height": 400,
                "display": "notebook",
            },
        )
    ]


def test_show_ui_serves_explicit_browser_display(monkeypatch):
    calls = []
    store = object()
    monkeypatch.setattr(app, "AppState", lambda: store)
    monkeypatch.setattr(
        app, "serve", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    client = FakeAppClient()
    client.show_app(display="browser")

    assert calls[0][0] == (client.config, store)
    assert calls[0][1]["compact"] is False
    assert calls[0][1]["display"] == "browser"


class FakeAppClient(ClientAppMixin):
    def __init__(self):
        self._config = ClientConfig(api_url="https://api.example.test")

    @property
    def config(self) -> ClientConfig:
        return self._config
