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


def get_app_url(
    base_url: str,
    ws_url: str,
    *,
    compact: bool = True,
    scheme: Literal["dark", "light", "auto"] | None = None,
    service: ServiceProvider | None = None,
) -> str:
    query = get_query_args(
        ws_url=ws_url,
        compact=compact,
        service=service,
        scheme=scheme if scheme != "auto" else None,
    )
    return f"{base_url}/index.html{query}"


def get_query_args(
    ws_url: str | None = None,
    compact: bool = True,
    scheme: Literal["dark", "light"] | None = None,
    service: ServiceProvider | None = None,
    nocache: bool = True,
) -> str:
    params: dict[str, str] = {}

    if nocache:
        params["_t"] = str(int(time.time()))

    if ws_url:
        params["ws"] = ws_url

    if compact:
        params["compact"] = "1"

    if scheme is not None:
        params["scheme"] = scheme

    if service is not None:
        params["service"] = _base64url_json(service)

    return f"?{urlencode(params)}" if params else ""


def _base64url_json(value: BaseModel) -> str:
    data = value.model_dump(mode="json", exclude_none=True)
    json_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("ascii").rstrip("=")
