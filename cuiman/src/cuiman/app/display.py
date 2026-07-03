#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

import json

from IPython.display import HTML, DisplayObject


def create_app_display_object(
    app_url: str,
    auto_scheme: bool,
    width: int | str,
    height: int | str,
) -> DisplayObject:
    if auto_scheme:
        return _get_iframe_auto_scheme_html(
            app_url,
            width=width,
            height=height,
        )
    else:
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


def _get_iframe_auto_scheme_html(
    base_src: str,
    *,
    width: int | str,
    height: int | str,
) -> HTML:
    return HTML(f"""
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
