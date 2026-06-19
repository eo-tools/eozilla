#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from typing import Literal

import time

import base64
import json
from urllib.parse import urlencode

from pydantic import BaseModel

from .service import ServiceProvider


def create_app_url(
    base_url: str,
    ws_url: str,
    *,
    compact: bool = True,
    debug: bool = False,
    scheme: Literal["dark", "light", "auto"] | None = None,
    service: ServiceProvider | None = None,
) -> str:
    if base_url.startswith("https://") and ws_url.startswith("ws://"):
        raise ValueError(
            f"Cannot use a URL {base_url} with an insecure WebSocket "
            f"URL at {ws_url}. Use an HTTP URL, mount the app locally, or serve the "
            "backend with TLS so the WebSocket URL is wss://."
        )
    query = get_query_args(
        ws_url=ws_url,
        compact=compact,
        debug=debug,
        scheme=scheme if scheme != "auto" else None,
        service=service,
    )
    return f"{base_url}{'' if base_url.endswith('/') else '/'}index.html{query}"


def get_query_args(
    compact: bool = True,
    debug: bool = False,
    nocache: bool = True,
    scheme: Literal["dark", "light"] | None = None,
    service: ServiceProvider | None = None,
    ws_url: str | None = None,
) -> str:
    params: dict[str, str] = {}

    if compact:
        params["compact"] = "1"

    if debug:
        params["debug"] = "1"

    if scheme is not None:
        params["scheme"] = scheme

    if nocache:
        params["_t"] = str(int(time.time()))

    if service is not None:
        params["service"] = _base64url_json(service)

    if ws_url:
        params["ws"] = ws_url

    return f"?{urlencode(params)}" if params else ""


def _base64url_json(value: BaseModel) -> str:
    data = value.model_dump(mode="json", exclude_none=True)
    json_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii").rstrip("=")
