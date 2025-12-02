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
    url, data = prepare_login(auth_config)
    with httpx.Client() as client:
        response = client.post(url, data=data)
        return process_login_response(response)


def prepare_login(config: AuthConfig) -> tuple[str, dict[str, str | None]]:
    if not config.auth_url:
        raise ValueError("Authentication URL must be set.")
    if not config.username or not config.password:
        raise ValueError(
            "Username and password must be set for authentication type 'login'."
        )
    return config.auth_url, {"username": config.username, "password": config.password}


def process_login_response(response: httpx.Response) -> Any:
    response.raise_for_status()
    # noinspection PyBroadException
    try:
        # Accept JSON ...
        token_data = response.json()
    except Exception:
        # ... or plain-text tokens
        token_data = response.text.strip()
    return parse_token(token_data)


def parse_token(token_data: Any) -> str:
    token: str | None = None
    if isinstance(token_data, str):
        token = token_data
    elif isinstance(token_data, dict):
        token = token_data.get("token")
        if not token:
            for k, v in token_data.items():
                if str(k).lower().endswith("token"):
                    token = v
                    break
        if token is None:
            raise RuntimeError(
                "Login succeeded, but no token has been returned by server."
            )
    if not isinstance(token, str):
        raise RuntimeError(
            f"Login succeeded, but token returned by server has wrong type. "
            f"Expected str, but got {type(token).__name__}."
        )
    if not token:
        raise RuntimeError("Login succeeded, but token returned by server is empty.")
    return token
