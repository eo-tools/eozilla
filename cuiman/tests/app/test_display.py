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
    assert 'width="320px"' in display_object.data
    assert 'height="75vh"' in display_object.data
    assert 'style="border: 0; width: 320px; height: 75vh;"' in display_object.data
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
    assert 'iframe.height = "600px"' in display_object.data


def test_create_app_display_object_uses_jupyter_proxy():
    display_object = create_app_display_object(
        "https://app.example.test/index.html?service=client",
        auto_scheme=False,
        width="100%",
        height=600,
        proxy_port=8765,
    )

    assert "const proxyPort = 8765" in display_object.data
    assert "function getJupyterProxyUrl(port, path)" in display_object.data
    assert "document.body.dataset.baseUrl" in display_object.data
    assert "`${basePath}proxy/${port}/${path}`" in display_object.data
    assert "async function isJupyterProxyAvailable(url)" in display_object.data
    assert 'fetch(url, { method: "GET" })' in display_object.data
    assert 'getJupyterProxyUrl(proxyPort, "ws")' in display_object.data
    assert 'src.searchParams.set("ws", wsUrl.toString())' in display_object.data


def test_create_app_display_object_uses_proxy_for_local_app():
    display_object = create_app_display_object(
        "http://127.0.0.1:8765/index.html?service=client",
        auto_scheme=False,
        width="100%",
        height=600,
        proxy_port=8765,
        proxy_app=True,
    )

    assert 'src = getJupyterProxyUrl(proxyPort, "index.html")' in display_object.data
    assert "src.search = query" in display_object.data


def test_create_app_display_object_probes_proxy_in_auto_mode():
    display_object = create_app_display_object(
        "http://127.0.0.1:8765/index.html",
        auto_scheme=False,
        width="100%",
        height=600,
        proxy_port=8765,
        proxy_app=True,
        auto_proxy=True,
    )

    assert "(async () => {" in display_object.data
    assert "(await isJupyterProxyAvailable(proxyUrl))" in display_object.data
    assert "if (useProxy)" in display_object.data


def test_create_app_display_object_opens_browser_with_link_fallback():
    display_object = create_app_display_object(
        "http://127.0.0.1:8765/index.html",
        auto_scheme=False,
        width="100%",
        height=600,
        open_in_browser=True,
    )

    assert 'window.open(src.toString(), "_blank", "noopener")' in display_object.data
    assert 'link.textContent = "Open Cuiman app"' in display_object.data
