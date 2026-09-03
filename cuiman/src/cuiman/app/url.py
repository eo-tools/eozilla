#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from typing import Literal
from urllib.parse import urlencode


def create_app_url(
    base_url: str,
    *,
    compact: bool = True,
    debug: bool = False,
    scheme: Literal["dark", "light", "auto"] | None = None,
    launch_code: str | None = None,
) -> str:
    """Build an Eozilla App URL for a Cuiman server.

    The secure launch flow uses ``launch_code`` only. It contains no service
    configuration or credentials and is exchanged by the browser for an
    HttpOnly cookie.
    """
    query = get_query_args(
        compact=compact,
        debug=debug,
        scheme=scheme if scheme != "auto" else None,
        launch_code=launch_code,
    )
    return f"{base_url}{'' if base_url.endswith('/') else '/'}index.html{query}"


def get_query_args(
    compact: bool = True,
    debug: bool = False,
    scheme: Literal["dark", "light"] | None = None,
    launch_code: str | None = None,
) -> str:
    """Serialize public UI bootstrap settings into an app query string.

    ``launch_code`` is intentionally the only Cuiman-launch-specific value in
    the query. The SPA derives its same-origin WebSocket and proxy URLs after
    the launch exchange, so no server URL needs to be exposed here.
    """
    params: dict[str, str] = {}

    if compact:
        params["compact"] = "1"

    if debug:
        params["debug"] = "1"

    if scheme is not None:
        params["scheme"] = scheme

    if launch_code:
        params["launch"] = launch_code

    return f"?{urlencode(params)}" if params else ""
