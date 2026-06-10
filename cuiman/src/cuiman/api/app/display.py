#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

import base64
import json
from typing import Literal
from urllib.parse import urlencode
from contextlib import ExitStack
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import socket
from threading import Thread
from types import ModuleType
from importlib import resources

from IPython.display import HTML, display
from pydantic import BaseModel


_APP_SERVERS: list[tuple[ThreadingHTTPServer, Thread]] = []
# noinspection PyAbstractClass
_APP_RESOURCE_STACK = ExitStack()


AppColorScheme = Literal["dark", "light"]
AppColorSchemeInput = AppColorScheme | Literal["auto"] | None

ServiceProviderType = Literal["test", "dev", "custom", "system"]
ServiceProviderOption = bool | int | float | str


class ServiceProviderMeta(BaseModel):
    type: ServiceProviderType
    title: str
    description: str | None = None
    disabled: bool | None = None
    hidden: bool | None = None


class SerializedAppConfig(BaseModel):
    serviceProviderId: str
    serviceProviderMeta: ServiceProviderMeta
    serviceProviderOptions: dict[str, ServiceProviderOption] = {}


def display_packaged_app_iframe(
    package: str | ModuleType,
    resource_dir: str = "app",
    *,
    compact: bool = True,
    config: SerializedAppConfig | None = None,
    scheme: AppColorSchemeInput = "auto",
    width: str = "100%",
    height: int = 700,
) -> None:
    resource = resources.files(package).joinpath(resource_dir)
    build_dir = _APP_RESOURCE_STACK.enter_context(resources.as_file(resource))

    display_app_iframe(
        build_dir,
        compact=compact,
        config=config,
        scheme=scheme,
        width=width,
        height=height,
    )


def display_app_iframe(
    build_dir: str | Path,
    *,
    compact: bool = True,
    config: SerializedAppConfig | None = None,
    scheme: AppColorSchemeInput = "auto",
    width: str = "100%",
    height: int = 700,
) -> None:
    base_url = _serve_directory(Path(build_dir))

    if scheme == "auto":
        query = get_query_args(compact=compact, config=config, scheme=None)
        _display_iframe_auto_scheme_html(
            f"{base_url}/index.html{query}",
            width=width,
            height=height,
        )
        return

    query = get_query_args(compact=compact, config=config, scheme=scheme)
    _display_iframe_html(
        f"{base_url}/index.html{query}",
        width=width,
        height=height,
    )


def _display_iframe_html(
    src: str,
    *,
    width: str,
    height: int,
) -> None:
    display(
        HTML(
            f"""
            <iframe
                src={json.dumps(src)}
                width={json.dumps(width)}
                height={json.dumps(str(height))}
                style={json.dumps(f"border: 0; width: {width}; height: {height}px;")}
                allow="clipboard-read; clipboard-write"
            ></iframe>
            """
        )
    )


def _display_iframe_auto_scheme_html(
    base_src: str,
    *,
    width: str,
    height: int,
) -> None:
    display(
        HTML(
            f"""
            <div class="eozilla-frame-root"></div>
            <script>
            (() => {{
              function detectJupyterScheme() {{
                const body = document.body;
                const root = document.documentElement;

                const themeLight =
                  body.getAttribute("data-jp-theme-light") ??
                  root.getAttribute("data-jp-theme-light");

                if (themeLight === "true") return "light";
                if (themeLight === "false") return "dark";

                const bg =
                  getComputedStyle(root).getPropertyValue("--jp-layout-color0") ||
                  getComputedStyle(body).backgroundColor;

                const match = bg.match(/\\d+/g);
                if (match && match.length >= 3) {{
                  const [r, g, b] = match.slice(0, 3).map(Number);
                  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
                  return luminance < 0.5 ? "dark" : "light";
                }}

                return null;
              }}

              const root = document.currentScript.previousElementSibling;
              const scheme = detectJupyterScheme();
              const src = new URL({json.dumps(base_src)}, window.location.href);

              if (scheme) {{
                src.searchParams.set("scheme", scheme);
              }}

              const iframe = document.createElement("iframe");
              iframe.src = src.toString();
              iframe.width = {json.dumps(width)};
              iframe.height = {json.dumps(str(height))};
              iframe.style.border = "0";
              iframe.style.width = {json.dumps(width)};
              iframe.style.height = {json.dumps(f"{height}px")};
              iframe.allow = "clipboard-read; clipboard-write";

              root.replaceChildren(iframe);
            }})();
            </script>
            """
        )
    )


def get_query_args(
    compact: bool = True,
    scheme: AppColorScheme | None = None,
    config: SerializedAppConfig | None = None,
) -> str:
    params: dict[str, str] = {}

    if compact:
        params["compact"] = "1"

    if scheme is not None:
        params["scheme"] = scheme

    if config is not None:
        params["config"] = _base64url_json(config)

    return f"?{urlencode(params)}" if params else ""


def _base64url_json(value: BaseModel) -> str:
    data = value.model_dump(mode="json", exclude_none=True)
    json_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii").rstrip("=")


def _serve_directory(directory: Path) -> str:
    directory = directory.resolve()
    port = _find_free_port()

    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    _APP_SERVERS.append((server, thread))
    return f"http://127.0.0.1:{port}"


def _find_free_port() -> int:
    with socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
