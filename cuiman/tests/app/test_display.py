#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import base64
import json
import re
import shutil
import subprocess
from importlib import resources

import pytest
from IPython.display import HTML

from cuiman.app.display import create_app_display_object

_NODE = shutil.which("node")


def _get_display_config(display_object: HTML) -> dict:
    match = re.search(
        r'<script type="application/json" class="eozilla-frame-config">\s*'
        r"(.*?)\s*</script>",
        display_object.data,
        re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


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
    assert "new URL(baseSrc, window.location.href)" in display_object.data
    assert 'src.searchParams.set("scheme", scheme)' in display_object.data
    assert _get_display_config(display_object) == {
        "baseSrc": "https://example.test/app",
        "autoScheme": True,
        "width": "100%",
        "height": "600px",
        "proxyPort": None,
        "proxyApp": False,
        "autoProxy": False,
        "openInBrowser": False,
    }


def test_create_app_display_object_uses_jupyter_proxy():
    display_object = create_app_display_object(
        "https://app.example.test/index.html?service=client",
        auto_scheme=False,
        width="100%",
        height=600,
        proxy_port=8765,
    )

    assert _get_display_config(display_object)["proxyPort"] == 8765
    assert "function getJupyterBaseUrl()" in display_object.data
    assert '"jupyter-config-data"' in display_object.data
    assert ").baseUrl" in display_object.data
    assert "`${basePath}proxy/`" in display_object.data
    assert "function getJupyterProxyUrl(port, path)" in display_object.data
    assert "new URL(`${port}/${path}`, getJupyterProxyBaseUrl())" in (
        display_object.data
    )
    assert "async function isJupyterProxyAvailable(url)" in display_object.data
    assert 'fetch(url, { method: "GET" })' in display_object.data
    assert 'console.debug("[cuiman] Jupyter proxy probe"' in display_object.data
    assert 'console.debug("[cuiman] display setup"' in display_object.data
    assert 'console.debug("[cuiman] display target"' in display_object.data
    assert 'getJupyterProxyUrl(proxyPort, "ws")' in display_object.data
    assert "PROXY_QUERY_PARAM" in display_object.data
    assert 'src.searchParams.set("ws", wsUrl)' in display_object.data


def test_create_app_display_object_uses_proxy_for_local_app():
    display_object = create_app_display_object(
        "http://127.0.0.1:8765/index.html?service=client",
        auto_scheme=False,
        width="100%",
        height=600,
        proxy_port=8765,
        proxy_app=True,
    )

    assert _get_display_config(display_object)["proxyApp"] is True
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

    assert _get_display_config(display_object)["autoProxy"] is True
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

    assert _get_display_config(display_object)["openInBrowser"] is True
    assert 'window.open(src.toString(), "_blank", "noopener")' in display_object.data
    assert 'link.textContent = "Open Cuiman app"' in display_object.data


def test_create_app_display_object_escapes_script_end_in_config():
    app_url = "https://example.test/</script><script>alert(1)</script>"

    display_object = create_app_display_object(
        app_url,
        auto_scheme=True,
        width="100%",
        height=600,
    )

    assert "\\u003c/script>\\u003cscript>alert(1)\\u003c/script>" in (
        display_object.data
    )
    assert _get_display_config(display_object)["baseSrc"] == app_url


def test_notebook_display_script_is_package_data():
    script = (
        resources.files("cuiman.app")
        .joinpath("notebook-display.js")
        .read_text(encoding="utf-8")
    )

    display_object = create_app_display_object(
        "https://example.test/app",
        auto_scheme=True,
        width="100%",
        height=600,
    )

    assert script in display_object.data
    assert "@typedef {Object} NotebookDisplayConfig" in script


@pytest.mark.skipif(_NODE is None, reason="Node.js is not installed")
def test_notebook_display_passes_local_url_proxy_base():
    service = {
        "id": "client",
        "meta": {"type": "custom", "title": "Client"},
        "options": {
            "apiUrl": "http://localhost:8080/process/?x=1#result",
            "authUrl": "http://127.0.0.1:9090/auth/login",
            "externalUrl": "https://api.example.test/process/",
            "nested": {
                "socketUrl": "ws://[::1]:7070/events",
                "defaultPortUrl": "http://tools.localhost/health",
            },
        },
    }
    service_json = json.dumps(service, separators=(",", ":")).encode()
    encoded_service = base64.urlsafe_b64encode(service_json).decode("ascii").rstrip("=")
    display_object = create_app_display_object(
        f"http://127.0.0.1:8765/index.html?service={encoded_service}",
        auto_scheme=False,
        width="100%",
        height=600,
        proxy_port=8765,
        proxy_app=True,
        auto_proxy=False,
    )
    config_json = json.dumps(_get_display_config(display_object))
    script = (
        resources.files("cuiman.app")
        .joinpath("notebook-display.js")
        .read_text(encoding="utf-8")
    )
    node_script = (
        """
class HTMLScriptElement {}
class HTMLElement {
  replaceChildren(child) {
    this.child = child;
  }
}

const root = new HTMLElement();
const configElement = new HTMLScriptElement();
configElement.textContent = JSON.stringify(CONFIG);
configElement.previousElementSibling = root;
const scriptElement = { previousElementSibling: configElement };
const jupyterConfigElement = {
  textContent: JSON.stringify({ baseUrl: "/user/test/" }),
};

globalThis.HTMLScriptElement = HTMLScriptElement;
globalThis.HTMLElement = HTMLElement;
globalThis.document = {
  currentScript: scriptElement,
  body: { dataset: {}, getAttribute: () => null },
  documentElement: { dataset: {}, getAttribute: () => null },
  getElementById: (id) =>
    id === "jupyter-config-data" ? jupyterConfigElement : null,
  createElement: () => ({ style: {} }),
};
globalThis.window = {
  location: new URL("https://hub.example/user/test/lab/tree/test.ipynb"),
};
globalThis.console = { debug: () => {} };
globalThis.fetch = async () => ({ ok: true, status: 200 });
""".replace("CONFIG", config_json)
        + script
        + """

const target = new URL(root.child.src);
const encodedService = target.searchParams.get("service");
const service = JSON.parse(
  Buffer.from(encodedService, "base64url").toString("utf8"),
);
process.stdout.write(JSON.stringify({
  appUrl: `${target.origin}${target.pathname}`,
  proxy: target.searchParams.get("proxy"),
  apiUrl: service.options.apiUrl,
  authUrl: service.options.authUrl,
  externalUrl: service.options.externalUrl,
  socketUrl: service.options.nested.socketUrl,
  defaultPortUrl: service.options.nested.defaultPortUrl,
}));
"""
    )

    assert _NODE is not None
    result = subprocess.run(  # noqa: S603
        [_NODE],
        input=node_script,
        text=True,
        capture_output=True,
        check=True,
    )

    assert json.loads(result.stdout) == {
        "appUrl": "https://hub.example/user/test/proxy/8765/index.html",
        "proxy": "https://hub.example/user/test/proxy/",
        "apiUrl": "http://localhost:8080/process/?x=1#result",
        "authUrl": "http://127.0.0.1:9090/auth/login",
        "externalUrl": "https://api.example.test/process/",
        "socketUrl": "ws://[::1]:7070/events",
        "defaultPortUrl": "http://tools.localhost/health",
    }
