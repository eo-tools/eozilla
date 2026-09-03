#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from urllib.parse import parse_qs, urlsplit

from cuiman.app import url


def test_create_app_url_omits_auto_scheme():
    app_url = url.create_app_url(
        "http://localhost:5173/",
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
        "compact": ["1"],
        "debug": ["1"],
    }


def test_get_query_args_encodes_public_options_and_launch_code():
    query_string = url.get_query_args(
        compact=True,
        scheme="dark",
        launch_code="opaque-code",
    )

    query = parse_qs(urlsplit(query_string).query)
    assert query["compact"] == ["1"]
    assert query["scheme"] == ["dark"]
    assert query["launch"] == ["opaque-code"]
    assert "debug" not in query


def test_get_query_args_returns_empty_string_without_params():
    assert url.get_query_args(compact=False) == ""
