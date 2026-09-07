#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Explicit credential prompts and browser login shared by Python and the CLI."""

import asyncio
import os
import secrets
import threading
import time
import webbrowser

import typer

from .config import (
    ApiKeyAuthConfig,
    AuthConfigBase,
    BasicAuthConfig,
    LoginAuthConfig,
    OAuth2AuthConfig,
    OidcAuthConfig,
    TokenAuthConfig,
)
from .oidc import (
    LoopbackCallbackServer,
    build_authorization_url,
    discover_oidc_provider,
    exchange_oidc_code,
    generate_pkce_verifier,
    parse_callback_parameters,
)

OIDC_LOGIN_TIMEOUT = 300.0
"""Seconds to wait for an OpenID Connect authorization callback."""


def prompt_auth(auth: AuthConfigBase, *, no_browser: bool = False) -> AuthConfigBase:
    """Collect credentials without modifying or persisting the original config."""
    # Construct a fresh model so temporary interaction cannot persist credentials.
    values = auth.to_public_dict()
    if isinstance(auth, OidcAuthConfig):
        return _login_oidc(OidcAuthConfig(**values), no_browser=no_browser)
    if isinstance(auth, (BasicAuthConfig, LoginAuthConfig, OAuth2AuthConfig)):
        if (
            isinstance(auth, OAuth2AuthConfig)
            and auth.grant_type == "client_credentials"
        ):
            raise ValueError(
                "Provide OAuth2 client_credentials through environment variables "
                "or Python configuration."
            )
        values.update(_prompt_for_username_password(auth.username))
        if isinstance(auth, OAuth2AuthConfig) and auth.client_secret is not None:
            values["client_secret"] = auth.client_secret
    elif isinstance(auth, TokenAuthConfig):
        values["access_token"] = _prompt_for_secret("API access token")
    elif isinstance(auth, ApiKeyAuthConfig):
        values["api_key"] = _prompt_for_secret("API access key")
    return type(auth)(**values)


async def prompt_auth_async(
    auth: AuthConfigBase, *, no_browser: bool = False
) -> AuthConfigBase:
    """Run explicit interaction off the event loop, cancelling browser waits."""
    if not isinstance(auth, OidcAuthConfig):
        return await asyncio.to_thread(prompt_auth, auth, no_browser=no_browser)
    cancelled = threading.Event()
    try:
        return await asyncio.to_thread(
            _login_oidc,
            OidcAuthConfig(**auth.to_public_dict()),
            no_browser=no_browser,
            cancelled=cancelled,
        )
    except asyncio.CancelledError:
        cancelled.set()
        raise


def _login_oidc(
    auth: OidcAuthConfig,
    *,
    no_browser: bool,
    cancelled: threading.Event | None = None,
) -> OidcAuthConfig:
    """Complete an OIDC Authorization Code login through a loopback callback."""
    discovery = discover_oidc_provider(auth)
    verifier = generate_pkce_verifier()
    state = secrets.token_urlsafe(32)
    with LoopbackCallbackServer() as callback_server:
        authorization_url = build_authorization_url(
            discovery,
            auth,
            callback_server.redirect_uri,
            state,
            verifier,
        )
        if no_browser:
            typer.echo(f"Open this URL to log in:\n{authorization_url}")
        elif not webbrowser.open(authorization_url):
            raise ValueError(
                "Could not open a browser for OIDC login. "
                "Use 'cuiman login --no-browser' to print the authorization URL."
            )
        parameters = _wait_for_callback(callback_server, cancelled)
        code = parse_callback_parameters(parameters, state)
        result = exchange_oidc_code(
            discovery,
            auth,
            code,
            verifier,
            callback_server.redirect_uri,
        )
    return auth.model_copy(
        update={
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
        }
    )


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
