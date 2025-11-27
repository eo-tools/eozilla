#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import httpx

from .config import AuthConfig


def login(auth_config: AuthConfig) -> Any:
    """
    Performs a synchronous login (username+password → token)
    and returns a token.

    Args:
        auth_config: authentication configuration.

    Returns:
        An access token either as JSON or plain text.
    """
    data = prepare_login(auth_config)
    with httpx.Client() as client:
        r = client.post(auth_config.auth_url, data=data)
        return process_login_response(r)


def prepare_login(config: AuthConfig) -> dict[str, str | None]:
    if not config.auth_url:
        raise ValueError("Authentication URL must be set.")
    if not config.username or not config.password:
        raise ValueError(
            "Username and password must be set for authentication type 'login'."
        )
    return {"username": config.username, "password": config.password}


def process_login_response(response: httpx.Response) -> Any:
    response.raise_for_status()
    # noinspection PyBroadException
    try:
        # Accept JSON ...
        token = response.json().get("token")
    except Exception:
        # ... or plain-text tokens
        token = response.text.strip()
    if not token:
        raise RuntimeError("Login succeeded but no token returned by server.")
    return token
