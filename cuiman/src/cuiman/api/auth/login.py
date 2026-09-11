#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import httpx2

from .config import LoginAuthConfig


def prepare_login(config: LoginAuthConfig) -> tuple[str, dict[str, str]]:
    """Build a proprietary username/password login request."""
    if not config.username or not config.password:
        raise ValueError(
            "Username and password must be set for authentication type 'login'."
        )
    return str(config.login_url), {
        "username": config.username,
        "password": config.password,
    }


def process_login_response(response: httpx2.Response) -> str:
    """Parse an access token from a proprietary login response."""
    response.raise_for_status()
    try:
        token_data = response.json()
    except Exception:  # noqa: BLE001 - proprietary endpoints may return plain text
        token_data = response.text.strip()
    return parse_token(token_data)


def parse_token(token_data: Any) -> str:
    """Extract a token string from common proprietary response shapes."""
    token: Any = None
    if isinstance(token_data, str):
        token = token_data
    elif isinstance(token_data, dict):
        token = _find_token(token_data)
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


def _find_token(token_data: dict) -> Any:
    for key in (
        "token",
        "authToken",
        "auth_token",
        "accessToken",
        "access_token",
        "apiToken",
        "api_token",
    ):
        if key in token_data:
            return token_data[key]

    for value in token_data.values():
        if isinstance(value, dict):
            token = _find_token(value)
            if token is not None:
                return token
    return None
