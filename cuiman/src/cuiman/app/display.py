#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

import json
from importlib import resources

from IPython.display import HTML, DisplayObject

_NOTEBOOK_DISPLAY_SCRIPT = (
    resources.files("cuiman.app")
    .joinpath("notebook-display.js")
    .read_text(encoding="utf-8")
)


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
    config = {
        "baseSrc": base_src,
        "autoScheme": auto_scheme,
        "width": _norm_size(width),
        "height": _norm_size(height),
        "proxyPort": proxy_port,
        "proxyApp": proxy_app,
        "autoProxy": auto_proxy,
        "openInBrowser": open_in_browser,
    }
    config_json = json.dumps(config, separators=(",", ":")).replace("<", "\\u003c")

    # Inline the package resource so notebook output needs no additional asset URL.
    return HTML(f"""
            <div class="eozilla-frame-root"></div>
            <script type="application/json" class="eozilla-frame-config">
              {config_json}
            </script>
            <script>
{_NOTEBOOK_DISPLAY_SCRIPT}
            </script>
            """)


def _norm_size(size: int | float | str) -> str:
    if isinstance(size, str):
        return size
    return f"{size}px"
