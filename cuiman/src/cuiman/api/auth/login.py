#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from typing import Any

import httpx
from pydantic import BaseModel

from .config import LoginAuthConfig


class TokenResult(BaseModel):
    """Access and optional refresh tokens returned by an authentication service."""

    access_token: str
    refresh_token: str | None = None


def login(auth_config: LoginAuthConfig) -> str:
    """Log in through a proprietary endpoint and return its access token."""
    return login_for_tokens(auth_config).access_token


def login_for_tokens(auth_config: LoginAuthConfig) -> TokenResult:
    """Log in through a proprietary endpoint and parse its token response."""
    url, data = prepare_login(auth_config)
    with httpx.Client() as client:
        response = client.post(url, data=data)
        return process_login_response_for_tokens(response)


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


def process_login_response(response: httpx.Response) -> str:
    """Parse an access token from a proprietary login response."""
    response.raise_for_status()
    try:
        token_data = response.json()
    except Exception:  # noqa: BLE001 - proprietary endpoints may return plain text
        token_data = response.text.strip()
    return parse_token(token_data)


def process_login_response_for_tokens(response: httpx.Response) -> TokenResult:
    """Parse access and optional refresh tokens from a login response."""
    response.raise_for_status()
    try:
        token_data = response.json()
    except json.JSONDecodeError:
        token_data = response.text.strip()
    access_token = parse_token(token_data)
    refresh_token = None
    if isinstance(token_data, dict):
        refresh_token = token_data.get("refresh_token")
    return TokenResult(access_token=access_token, refresh_token=refresh_token)


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
