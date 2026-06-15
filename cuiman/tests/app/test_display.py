#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from IPython.display import HTML

from cuiman.app.display import create_app_display_object


def test_create_app_display_object_returns_plain_iframe_html():
    display_object = create_app_display_object(
        "https://example.test/app?x=1&y=two",
        auto_scheme=False,
        width=320,
        height="75vh",
    )

    assert isinstance(display_object, HTML)
    assert 'src="https://example.test/app?x=1&y=two"' in display_object.data
    assert "width=320" in display_object.data
    assert 'height="75vh"' in display_object.data
    assert 'style="border: 0; width: 320; height: 75vh;"' in display_object.data
    assert 'allow="clipboard-read; clipboard-write"' in display_object.data


def test_create_app_display_object_returns_auto_scheme_html():
    display_object = create_app_display_object(
        "https://example.test/app",
        auto_scheme=True,
        width="100%",
        height=600,
    )

    assert isinstance(display_object, HTML)
    assert "detectJupyterScheme()" in display_object.data
    assert 'new URL("https://example.test/app", window.location.href)' in (
        display_object.data
    )
    assert 'src.searchParams.set("scheme", scheme)' in display_object.data
    assert 'iframe.width = "100%"' in display_object.data
    assert "iframe.height = 600" in display_object.data
