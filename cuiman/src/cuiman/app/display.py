#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

import json

from IPython.display import HTML, DisplayObject


def create_app_display_object(
    app_url: str,
    *,
    auto_scheme: bool,
    width: int | str,
    height: int | str,
    proxy_port: int | None = None,
    proxy_app: bool = False,
    auto_proxy: bool = False,
    open_in_browser: bool = False,
) -> DisplayObject:
    """Create the notebook display object for the Cuiman app."""
    if auto_scheme or proxy_port is not None or open_in_browser:
        return _get_iframe_script_html(
            app_url,
            auto_scheme=auto_scheme,
            width=width,
            height=height,
            proxy_port=proxy_port,
            proxy_app=proxy_app,
            auto_proxy=auto_proxy,
            open_in_browser=open_in_browser,
        )
    return _get_iframe_html(
        app_url,
        width=width,
        height=height,
    )


def _get_iframe_html(
    src: str,
    *,
    width: int | str,
    height: int | str,
) -> HTML:
    return HTML(f"""
            <iframe
                src={json.dumps(src)}
                width={json.dumps(_norm_size(width))}
                height={json.dumps(_norm_size(height))}
                style={json.dumps(f"border: 0; width: {_norm_size(width)}; height: {_norm_size(height)};")}
                allow="clipboard-read; clipboard-write"
            ></iframe>
            """)


def _get_iframe_script_html(
    base_src: str,
    *,
    auto_scheme: bool,
    width: int | str,
    height: int | str,
    proxy_port: int | None,
    proxy_app: bool,
    auto_proxy: bool,
    open_in_browser: bool,
) -> HTML:
    return HTML(f"""
            <div class="eozilla-frame-root"></div>
            <script>
            (async () => {{
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

              function getJupyterProxyUrl(port, path) {{
                const baseUrl =
                  document.body.dataset.baseUrl ??
                  document.documentElement.dataset.baseUrl ??
                  "/";
                const basePath = baseUrl.endsWith("/") ? baseUrl : `${{baseUrl}}/`;
                return new URL(
                  `${{basePath}}proxy/${{port}}/${{path}}`,
                  window.location.origin,
                );
              }}

              async function isJupyterProxyAvailable(url) {{
                try {{
                  const response = await fetch(url, {{ method: "GET" }});
                  return response.ok;
                }} catch {{
                  return false;
                }}
              }}

              const root = document.currentScript.previousElementSibling;
              let src = new URL({json.dumps(base_src)}, window.location.href);
              const proxyPort = {json.dumps(proxy_port)};

              if (proxyPort !== null) {{
                const proxyUrl = getJupyterProxyUrl(proxyPort, "index.html");
                const wsUrl = getJupyterProxyUrl(proxyPort, "ws");
                wsUrl.protocol =
                  window.location.protocol === "https:" ? "wss:" : "ws:";

                const useProxy =
                  !{json.dumps(auto_proxy)} ||
                  (await isJupyterProxyAvailable(proxyUrl));

                if (useProxy && {json.dumps(proxy_app)}) {{
                  const query = src.search;
                  src = getJupyterProxyUrl(proxyPort, "index.html");
                  src.search = query;
                }}

                if (useProxy) {{
                  src.searchParams.set("ws", wsUrl.toString());
                }}
              }}

              if ({json.dumps(auto_scheme)}) {{
                const scheme = detectJupyterScheme();
                if (scheme) {{
                  src.searchParams.set("scheme", scheme);
                }}
              }}

              if ({json.dumps(open_in_browser)}) {{
                const opened = window.open(src.toString(), "_blank", "noopener");
                if (!opened) {{
                  const link = document.createElement("a");
                  link.href = src.toString();
                  link.target = "_blank";
                  link.rel = "noopener";
                  link.textContent = "Open Cuiman app";
                  root.replaceChildren(link);
                }}
                return;
              }}

              const iframe = document.createElement("iframe");
              iframe.src = src.toString();
              iframe.width = {json.dumps(_norm_size(width))};
              iframe.height = {json.dumps(_norm_size(height))};
              iframe.style.border = "0";
              iframe.style.width = {json.dumps(_norm_size(width))};
              iframe.style.height = {json.dumps(_norm_size(height))};
              iframe.allow = "clipboard-read; clipboard-write";

              root.replaceChildren(iframe);
            }})();
            </script>
            """)


def _norm_size(size: int | float | str) -> str:
    if isinstance(size, str):
        return size
    return f"{size}px"
