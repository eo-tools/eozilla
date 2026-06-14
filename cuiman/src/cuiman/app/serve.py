#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from socket import socket
from typing import Literal, Any
from importlib.resources import files

from fastapi.staticfiles import StaticFiles
import remotestate as rs

from cuiman.api.config import ClientConfig
from .config import get_app_config
from .display import get_app_display_object
from .url import get_app_url

DIST_ENV_VAR = "EOZILLA_APP_DIST"


def serve(
    config: ClientConfig,
    ui_data: rs.Store,
    *,
    compact: bool = True,
    scheme: Literal["dark", "light", "auto"] = "auto",
    width: int | str = "100%",
    height: int | str = 600,
    open_in_browser: bool = False,
    open_in_cell: bool = True,
):
    host = "127.0.0.1"
    port = _find_free_port()
    app_base_url = f"http://{host}:{port}"

    ui_dist: str | StaticFiles | None = os.environ.get(DIST_ENV_VAR)
    if _is_url_str(ui_dist):
        app_base_url = ui_dist
        ui_dist = None
    else:
        if ui_dist:
            static_path = ui_dist
        else:
            static_path = files("cuiman.app").joinpath("dist")
        ui_dist = StaticFiles(directory=str(static_path), html=True)

    rs.serve(
        rs.Service(ui_data),
        ui_dist=ui_dist,
        host=host,
        port=port,
        open_browser=False,
        open_iframe=False,
    )

    app_url = get_app_url(
        app_base_url,
        f"ws://127.0.0.1:{port}/ws",
        compact=compact,
        scheme=scheme,
        config=get_app_config(config),
    )

    if open_in_browser:
        import webbrowser

        webbrowser.open(app_url)

    elif open_in_cell:
        from IPython.display import display

        display_object = get_app_display_object(
            app_url, auto_scheme=scheme == "auto", width=width, height=height
        )
        display(display_object)


def _find_free_port() -> int:
    with socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _is_url_str(value: Any) -> bool:
    return isinstance(value, str) and (
        value.startswith("http://") or value.startswith("https://")
    )
