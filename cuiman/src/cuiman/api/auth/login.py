#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import httpx
from pydantic import BaseModel

from .config import AuthConfig


class LoginResult(BaseModel):
    """Result of a login or token refresh operation."""

    access_token: str
    refresh_token: str | None = None


def login(auth_config: AuthConfig) -> Any:
    """
    Performs a synchronous login (username+password → token)
    and returns a token.

    Args:
        auth_config: authentication configuration.

    Returns:
        An access token either as JSON or plain text.
    """
    return login_for_tokens(auth_config).access_token


def login_for_tokens(auth_config: AuthConfig) -> LoginResult:
    """
    Performs a synchronous login and returns both
    access token and refresh token (if available).

    Args:
        auth_config: authentication configuration.

    Returns:
        A LoginResult with access_token and optional refresh_token.
    """
    url, data = prepare_login(auth_config)
    with httpx.Client() as client:
        response = client.post(url, data=data)
        return process_login_response_for_tokens(response)


def refresh_login(auth_config: AuthConfig) -> LoginResult:
    """
    Performs a synchronous token refresh using a refresh token.

    Args:
        auth_config: authentication configuration (must have refresh_token set).

    Returns:
        A LoginResult with the new access_token and optional new refresh_token.
    """
    url, data = prepare_refresh(auth_config)
    with httpx.Client() as client:
        response = client.post(url, data=data)
        return process_login_response_for_tokens(response)


def prepare_login(config: AuthConfig) -> tuple[str, dict[str, str | None]]:
    if not config.auth_url:
        raise ValueError("Authentication URL must be set.")
    if not config.username or not config.password:
        raise ValueError(
            "Username and password must be set for authentication type 'login'."
        )
    data: dict[str, str | None] = {
        "grant_type": config.grant_type,
        "username": config.username,
        "password": config.password,
    }
    if config.client_id:
        data["client_id"] = config.client_id
    if config.client_secret:
        data["client_secret"] = config.client_secret
    return config.auth_url, data


def prepare_refresh(config: AuthConfig) -> tuple[str, dict[str, str | None]]:
    if not config.auth_url:
        raise ValueError("Authentication URL must be set.")
    if not config.refresh_token:
        raise ValueError("Refresh token must be set for token refresh.")
    data: dict[str, str | None] = {
        "grant_type": "refresh_token",
        "refresh_token": config.refresh_token,
    }
    if config.client_id:
        data["client_id"] = config.client_id
    if config.client_secret:
        data["client_secret"] = config.client_secret
    return config.auth_url, data


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


def process_login_response_for_tokens(response: httpx.Response) -> LoginResult:
    response.raise_for_status()
    # noinspection PyBroadException
    try:
        token_data = response.json()
    except Exception:
        token_data = response.text.strip()
    access_token = parse_token(token_data)
    refresh_token = None
    if isinstance(token_data, dict):
        refresh_token = token_data.get("refresh_token")
    return LoginResult(access_token=access_token, refresh_token=refresh_token)


def parse_token(token_data: Any) -> str:
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
    # TODO: This is a more or less generic hack.
    #  Either we make the path to the token configurable or we
    #  allow clients to pass a token-obtaining function to their
    #  client API configuration.

    for k in (
        "token",
        "authToken",
        "auth_token",
        "accessToken",
        "access_token",
        "apiToken",
        "api_token",
    ):
        if k in token_data:
            return token_data[k]

    for v in token_data.values():
        if isinstance(v, dict):
            token = _find_token(v)
            if token is not None:
                return token

    return None
