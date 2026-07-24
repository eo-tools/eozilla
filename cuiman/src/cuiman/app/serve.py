import os
from importlib.resources import files
from typing import Literal

import remotestate as rs

from cuiman.api.config import ClientConfig
from cuiman.api.ishell import has_ishell

from .display import create_app_display_object
from .service import create_app_service_provider
from .url import create_app_url

DIST_ENV_VAR = "EOZILLA_APP_DIST"
"""Name of the environment variable that points to a folder with an app (dev) build."""

SchemeMode = Literal["dark", "light", "auto"]
"""The app's color scheme mode."""

DisplayMode = Literal["browser", "notebook", "none"]
"""The app's display mode."""

ProxyMode = Literal["auto", "never", "always"]
"""Strategy for routing notebook traffic through jupyter-server-proxy."""


def serve(
    config: ClientConfig,
    store: rs.Store,
    *,
    compact: bool = True,
    debug: bool = False,
    scheme: SchemeMode = "auto",
    width: int | str = "100%",
    height: int | str = 600,
    display: DisplayMode = "notebook",
    proxy: ProxyMode = "auto",
) -> rs.ServeResult:
    """Start the Cuiman app server and optionally display its user interface.

    The server always listens on the local loopback interface. When the app is
    embedded in a notebook, ``jupyter-server-proxy`` can expose that local
    server through the browser-visible Jupyter URL. This also supports remote
    JupyterLab and JupyterHub deployments without exposing the server port.

    Args:
        config: Client configuration made available to the app service.
        store: Remote state store shared by the Python client and web app.
        compact: Whether the app uses its compact layout.
        debug: Whether to enable app debug mode.
        scheme: App color scheme. ``"auto"`` follows the surrounding notebook
            theme when the app is embedded.
        width: Width of the embedded notebook iframe.
        height: Height of the embedded notebook iframe.
        display: Where to show the app. ``"notebook"`` embeds it in the
            current notebook, ``"browser"`` opens it in a browser, and
            ``"none"`` only starts the server. Browser requests from a notebook
            are opened by notebook-side JavaScript so that remote deployments
            use the user's browser.
        proxy: Whether notebook traffic uses ``jupyter-server-proxy``.
            ``"auto"`` checks for it from the notebook browser and falls back
            to the normal local URL when unavailable, ``"never"`` disables it,
            and ``"always"`` assumes it is configured on the Jupyter server.
            When enabled, URLs using loopback hosts in the app's client
            configuration are routed through the proxy as well.

    Returns:
        The running ``remotestate`` server result. Call its ``stop()`` method
        to stop the local server when the app is no longer needed.
    """
    app_dist = _get_app_dist_url_or_dir(os.environ.get(DIST_ENV_VAR))

    server = rs.serve(
        rs.Service(store),
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

    if display == "browser" and not has_ishell:
        import webbrowser

        webbrowser.open(app_url)
        return server

    if display in {"browser", "notebook"}:
        from IPython.display import display as ipython_display

        proxy_port = server.port if proxy != "never" else None
        proxy_app = proxy_port is not None and server.ui_base_url == server.server_url
        display_object = create_app_display_object(
            app_url,
            auto_scheme=scheme == "auto" and display == "notebook",
            width=width,
            height=height,
            proxy_port=proxy_port,
            proxy_app=proxy_app,
            auto_proxy=proxy == "auto",
            open_in_browser=display == "browser",
        )
        ipython_display(display_object)

    return server


def _get_app_dist_url_or_dir(dist_url_or_dir: str | None) -> str:
    if dist_url_or_dir:
        return dist_url_or_dir

    return str(files("cuiman.app").joinpath("dist"))
