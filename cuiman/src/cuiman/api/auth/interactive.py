# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Explicit credential prompts and browser interaction, without HTTP clients."""

import asyncio
import os
import threading
import time
import webbrowser
from urllib.parse import urlencode

import typer
from authlib.oauth2.rfc6749.parameters import parse_authorization_code_response

from .config import (
    ApiKeyAuthConfig,
    AuthConfigBase,
    BasicAuthConfig,
    LoginAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
)
from .oidc import LoopbackCallbackServer

OIDC_LOGIN_TIMEOUT = 300.0
"""Seconds to wait for an authorization callback."""


def prompt_auth(auth: AuthConfigBase) -> AuthConfigBase:
    """Collect credentials without modifying or persisting the input model."""
    values = auth.to_public_dict()
    if isinstance(auth, OAuth2AuthConfig) and auth.grant_type == "client_credentials":
        values["client_secret"] = _prompt_for_secret("Client secret")
    elif isinstance(auth, (BasicAuthConfig, LoginAuthConfig, OAuth2AuthConfig)):
        values.update(_prompt_for_username_password(auth.username))
        if isinstance(auth, OAuth2AuthConfig):
            values["client_secret"] = auth.client_secret
    elif isinstance(auth, TokenAuthConfig):
        values["access_token"] = _prompt_for_secret("API access token")
    elif isinstance(auth, ApiKeyAuthConfig):
        values["api_key"] = _prompt_for_secret("API access key")
    return type(auth)(**values)


def authorize(
    server: LoopbackCallbackServer,
    url: str,
    state: str,
    *,
    no_browser: bool,
    cancelled: threading.Event | None = None,
) -> str:
    """Receive a browser callback and let Authlib validate its state and code."""
    if no_browser:
        typer.echo(f"Open this URL to log in:\n{url}")
    elif not webbrowser.open(url):
        raise ValueError(
            "Could not open a browser. Use login(no_browser=True) to print the URL."
        )
    parameters = _wait_for_callback(server, cancelled)
    for name in ("state", "code", "error", "error_description"):
        if len(parameters.get(name, [])) > 1:
            raise ValueError(f"OIDC callback contains multiple {name} values.")
    response_url = server.redirect_uri + "?" + urlencode(parameters, doseq=True)
    return parse_authorization_code_response(response_url, state=state)["code"]


def _wait_for_callback(
    server: LoopbackCallbackServer, cancelled: threading.Event | None
) -> dict[str, list[str]]:
    if cancelled is None:
        return server.wait_for_callback(OIDC_LOGIN_TIMEOUT)
    deadline = time.monotonic() + OIDC_LOGIN_TIMEOUT
    while not cancelled.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for the OIDC authorization callback.")
        try:
            return server.wait_for_callback(min(remaining, 0.1))
        except TimeoutError:
            pass
    raise asyncio.CancelledError()


def _prompt_for_username_password(previous_username: str | None) -> dict[str, str]:
    username = typer.prompt(
        "Username",
        type=str,
        default=previous_username
        or os.environ.get("USER")
        or os.environ.get("USERNAME")
        or "",
    )
    return {"username": username, "password": _prompt_for_secret("Password")}


def _prompt_for_secret(text: str) -> str:
    return typer.prompt(text, type=str, hide_input=True)
