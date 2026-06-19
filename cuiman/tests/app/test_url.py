#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import base64
import json
from urllib.parse import parse_qs, urlsplit

from cuiman.app import url
from cuiman.app.service import ServiceProvider, ServiceProviderMeta


def decode_base64url_json(value: str) -> dict:
    padding = "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(value + padding))


def test_create_app_url_omits_auto_scheme(monkeypatch):
    monkeypatch.setattr(url.time, "time", lambda: 1234.9)

    app_url = url.create_app_url(
        "https://app.example.test",
        "ws://127.0.0.1:9876/ws",
        compact=True,
        debug=True,
        scheme="auto",
    )

    parts = urlsplit(app_url)
    assert parts.scheme == "https"
    assert parts.netloc == "app.example.test"
    assert parts.path == "/index.html"

    query = parse_qs(parts.query)
    assert query == {
        "_t": ["1234"],
        "ws": ["ws://127.0.0.1:9876/ws"],
        "compact": ["1"],
        "debug": ["1"],
    }


def test_get_query_args_encodes_explicit_options(monkeypatch):
    monkeypatch.setattr(url.time, "time", lambda: 9876)
    provider = ServiceProvider(
        id="client",
        meta=ServiceProviderMeta(
            type="custom",
            title="Client",
            description=None,
            disabled=None,
            hidden=True,
        ),
        options={"apiUrl": "https://api.example.test", "authType": None},
    )

    query_string = url.get_query_args(
        ws_url="ws://localhost/ws",
        compact=True,
        scheme="dark",
        service=provider,
    )

    query = parse_qs(urlsplit(query_string).query)
    assert query["_t"] == ["9876"]
    assert query["ws"] == ["ws://localhost/ws"]
    assert query["compact"] == ["1"]
    assert query["scheme"] == ["dark"]
    assert "debug" not in query

    assert decode_base64url_json(query["service"][0]) == {
        "id": "client",
        "meta": {
            "type": "custom",
            "title": "Client",
            "hidden": True,
        },
        "options": {"apiUrl": "https://api.example.test", "authType": None},
    }


def test_get_query_args_returns_empty_string_without_params():
    assert url.get_query_args(compact=False, nocache=False) == ""
