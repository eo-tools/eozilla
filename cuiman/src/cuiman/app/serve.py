#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from importlib.resources import files
from socket import socket
from typing import Any, Literal

from fastapi.staticfiles import StaticFiles
import remotestate as rs

from cuiman.api.config import ClientConfig
from .service import create_app_service_provider
from .display import create_app_display_object
from .url import create_app_url

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
    open_in_notebook: bool = True,
):
    # --- Serve the app

    server_host = "127.0.0.1"
    server_port = _find_free_port()

    app_dist_url, app_dist_dir = _get_app_dist_url_or_dir(
        dist_url_or_dir=os.environ.get(DIST_ENV_VAR),
        server_host=server_host,
        server_port=server_port,
    )

    rs.serve(
        rs.Service(ui_data),
        ui_dist=app_dist_dir,
        host=server_host,
        port=server_port,
        open_browser=False,
        open_iframe=False,
    )

    # --- Open the app

    app_url = create_app_url(
        app_dist_url,
        f"ws://{server_host}:{server_port}/ws",
        compact=compact,
        scheme=scheme,
        service=create_app_service_provider(config),
    )

    if open_in_browser:
        import webbrowser

        webbrowser.open(app_url)

    elif open_in_notebook:
        from IPython.display import display

        display_object = create_app_display_object(
            app_url, scheme == "auto", width, height
        )
        display(display_object)


def _get_app_dist_url_or_dir(
    dist_url_or_dir: str | None,
    server_host: str | None,
    server_port: int | None,
) -> tuple[str, StaticFiles | None]:
    server_host = "127.0.0.1" if server_host is None else server_host
    server_port = _find_free_port() if server_port is None else server_port
    dist_url = f"http://{server_host}:{server_port}"
    dist_dir: StaticFiles | None = None
    if isinstance(dist_url_or_dir, str) and dist_url_or_dir:
        if _is_url_str(dist_url_or_dir):
            dist_url = dist_url_or_dir
        else:
            dist_dir = StaticFiles(directory=dist_url_or_dir, html=True)
    else:
        # noinspection PyStringConversionWithoutDunderMethod
        directory = str(files("cuiman.app").joinpath("dist"))
        dist_dir = StaticFiles(directory=directory, html=True)
    return dist_url, dist_dir


def _find_free_port() -> int:
    with socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _is_url_str(value: Any) -> bool:
    return isinstance(value, str) and (
        value.startswith("http://") or value.startswith("https://")
    )
