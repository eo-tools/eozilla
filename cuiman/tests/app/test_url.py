#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from urllib.parse import parse_qs, urlsplit

import pytest

from cuiman.app import url
def test_create_app_url_raises_for_https_and_ws(monkeypatch):
    with pytest.raises(ValueError, match="Cannot use a URL https://app.example.test "):
        url.create_app_url(
            "https://app.example.test",
            "ws://127.0.0.1:9876/ws",
        )


def test_create_app_url_omits_auto_scheme(monkeypatch):
    monkeypatch.setattr(url.time, "time", lambda: 1234.9)

    app_url = url.create_app_url(
        "http://localhost:5173/",
        "ws://127.0.0.1:9876/ws",
        compact=True,
        debug=True,
        scheme="auto",
    )

    parts = urlsplit(app_url)
    assert parts.scheme == "http"
    assert parts.netloc == "localhost:5173"
    assert parts.path == "/index.html"

    query = parse_qs(parts.query)
    assert query == {
        "_t": ["1234"],
        "ws": ["ws://127.0.0.1:9876/ws"],
        "compact": ["1"],
        "debug": ["1"],
    }


def test_get_query_args_encodes_public_options_and_launch_code(monkeypatch):
    monkeypatch.setattr(url.time, "time", lambda: 9876)

    query_string = url.get_query_args(
        ws_url="ws://localhost/ws",
        compact=True,
        scheme="dark",
        launch_code="opaque-code",
    )

    query = parse_qs(urlsplit(query_string).query)
    assert query["_t"] == ["9876"]
    assert query["ws"] == ["ws://localhost/ws"]
    assert query["compact"] == ["1"]
    assert query["scheme"] == ["dark"]
    assert query["launch"] == ["opaque-code"]
    assert "debug" not in query


def test_get_query_args_returns_empty_string_without_params():
    assert url.get_query_args(compact=False, nocache=False) == ""
