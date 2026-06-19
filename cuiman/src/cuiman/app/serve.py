import os
from importlib.resources import files
from typing import Literal

import remotestate as rs

from cuiman.api.config import ClientConfig
from .display import create_app_display_object
from .service import create_app_service_provider
from .url import create_app_url

DIST_ENV_VAR = "EOZILLA_APP_DIST"


def serve(
    config: ClientConfig,
    ui_data: rs.Store,
    *,
    compact: bool = True,
    debug: bool = False,
    scheme: Literal["dark", "light", "auto"] = "auto",
    width: int | str = "100%",
    height: int | str = 600,
    display: Literal["browser", "notebook", "none"] = "notebook",
) -> rs.ServeResult:
    app_dist = _get_app_dist_url_or_dir(os.environ.get(DIST_ENV_VAR))

    server = rs.serve(
        rs.Service(ui_data),
        ui_dist=app_dist,
        host="127.0.0.1",
        display="none",
    )

    if display == "none":
        return server

    app_url = create_app_url(
        server.ui_base_url,
        server.ws_url,
        compact=compact,
        debug=debug,
        scheme=scheme,
        service=create_app_service_provider(config),
    )

    if display == "browser":
        import webbrowser

        webbrowser.open(app_url)

    elif display == "notebook":
        from IPython.display import display as ipython_display

        display_object = create_app_display_object(
            app_url, scheme == "auto", width, height
        )
        ipython_display(display_object)

    return server


def _get_app_dist_url_or_dir(dist_url_or_dir: str | None) -> str:
    if dist_url_or_dir:
        return dist_url_or_dir

    return str(files("cuiman.app").joinpath("dist"))
