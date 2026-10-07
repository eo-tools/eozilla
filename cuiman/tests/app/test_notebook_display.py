#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

"""Execute notebook display JavaScript with a minimal notebook DOM."""

import json
import shutil
import subprocess
from importlib import resources

import pytest

_NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(_NODE is None, reason="Node.js is required")

_HARNESS = """
const vm = require('node:vm');
const fs = require('node:fs');
const {
  script, notebookUrl, appUrl, proxyAvailable,
  displayName = null, openInBrowser = false, inspectBranding = false,
  invalidMarkup = false,
} = JSON.parse(
  fs.readFileSync(0, 'utf8')
);
class HTMLElement {
  replaceChildren(child) { this.child = child; }
}
class HTMLScriptElement extends HTMLElement {}
const root = new HTMLElement();
const config = new HTMLScriptElement();
config.previousElementSibling = root;
config.textContent = JSON.stringify({
  baseSrc: appUrl, autoScheme: false, width: '100%', height: '600px',
  proxyPort: 8765, proxyApp: true, autoProxy: true, openInBrowser, displayName,
});
const location = new URL(notebookUrl);
const logs = [];
const context = {
  URL, HTMLElement, HTMLScriptElement,
  console: { debug(message) { logs.push(message); } },
  window: { location, open() { return null; } },
  document: {
    currentScript: invalidMarkup ? null : { previousElementSibling: config },
    body: { dataset: {} }, documentElement: { dataset: {} },
    getElementById() { return null; },
    createElement() { return { style: {} }; },
  },
  fetch: async () => ({ ok: proxyAvailable, status: proxyAvailable ? 200 : 404 }),
};
Promise.resolve(vm.runInNewContext(script, context)).then(() => {
  process.stdout.write(inspectBranding
    ? JSON.stringify({ label: root.child.textContent, logs })
    : root.child.src);
}).catch(error => { console.error(error); process.exitCode = 1; });
"""


@pytest.mark.parametrize(
    "notebook_url,app_url,proxy_available,expected_url",
    [
        (
            "http://localhost:8888/lab",
            "http://127.0.0.1:8765/index.html?launch=test-code",
            False,
            "http://localhost:8765/index.html?launch=test-code",
        ),
        (
            "http://127.0.0.1:8888/lab",
            "http://localhost:8765/index.html?launch=test-code",
            False,
            "http://127.0.0.1:8765/index.html?launch=test-code",
        ),
        (
            "http://localhost:8888/lab",
            "http://127.0.0.1:8765/index.html?cuiman=1&scheme=dark",
            False,
            "http://localhost:8765/index.html?cuiman=1&scheme=dark",
        ),
        (
            "http://localhost:8888/lab",
            "http://127.0.0.1:8765/index.html?launch=test-code",
            True,
            "http://localhost:8888/proxy/8765/index.html?launch=test-code",
        ),
        (
            "https://hub.example.test/lab",
            "http://127.0.0.1:8765/index.html?launch=test-code",
            True,
            "https://hub.example.test/proxy/8765/index.html?launch=test-code",
        ),
        (
            "https://hub.example.test/lab",
            "http://127.0.0.1:8765/index.html?launch=test-code",
            False,
            "http://127.0.0.1:8765/index.html?launch=test-code",
        ),
        (
            "http://localhost:8888/lab",
            "https://app.example.test/index.html?launch=test-code",
            False,
            "https://app.example.test/index.html?launch=test-code",
        ),
        (
            "http://localhost:8888/lab",
            "http://127.0.0.1:8765/index.html",
            False,
            "http://127.0.0.1:8765/index.html",
        ),
    ],
)
def test_notebook_display_url(notebook_url, app_url, proxy_available, expected_url):
    script = (
        resources.files("cuiman.app")
        .joinpath("notebook-display.js")
        .read_text(encoding="utf-8")
    )
    # Execute only the fixed test harness and the repository's packaged script.
    result = subprocess.run(  # noqa: S603
        [_NODE, "-e", _HARNESS],
        input=json.dumps(
            {
                "script": script,
                "notebookUrl": notebook_url,
                "appUrl": app_url,
                "proxyAvailable": proxy_available,
            }
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    assert result.stdout == expected_url


@pytest.mark.parametrize("name", [None, 'Anolis <name> "quoted"'])
def test_notebook_link_and_debug_messages_use_display_name(name):
    result = run_branding_script(displayName=name)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["label"] == (f"Open {name} app" if name else "Open app")
    assert output["logs"] == [
        f"[{name or 'app'}] display setup",
        f"[{name or 'app'}] Jupyter proxy probe",
        f"[{name or 'app'}] display target",
    ]


def test_invalid_notebook_markup_has_neutral_error_before_config_is_available():
    result = run_branding_script(invalidMarkup=True)
    assert result.returncode == 1
    assert "Invalid notebook display markup" in result.stderr
    assert "Cuiman" not in result.stderr


def run_branding_script(**options):
    script = (
        resources.files("cuiman.app")
        .joinpath("notebook-display.js")
        .read_text(encoding="utf-8")
    )
    return subprocess.run(  # noqa: S603
        [_NODE, "-e", _HARNESS],
        input=json.dumps(
            dict(
                script=script,
                notebookUrl="http://localhost:8888/lab",
                appUrl="http://localhost:8765/index.html?launch=test-code",
                proxyAvailable=True,
                openInBrowser=True,
                inspectBranding=True,
                **options,
            )
        ),
        capture_output=True,
        text=True,
        timeout=10,
    )
