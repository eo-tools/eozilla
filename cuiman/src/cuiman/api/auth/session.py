#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Authentication lifecycle shared by clients, app launches, and the CLI.

This module selects acquisition and renewal operations and commits credentials.
Protocol helpers return token values; configuration and transport delegate here
without performing token updates themselves.
"""

from functools import partial
from typing import Awaitable, Callable, Mapping

import httpx2

from .config import (
    AuthConfigBase,
    LoginAuthConfig,
    OAuth2AuthConfig,
    OidcAuthConfig,
)
from .login import login
from .login_async import login_async
from .oauth2 import obtain_oauth2_tokens, renew_oauth2_tokens
from .oauth2_async import (
    obtain_oauth2_tokens_async,
    renew_oauth2_tokens_async,
)
from .oidc import renew_oidc_tokens
from .oidc_async import renew_oidc_tokens_async
from .tokens import TokenResult


class LoginRequiredError(ValueError):
    """Authentication requires credentials or an explicit interactive login."""


def has_auth_headers(auth: AuthConfigBase) -> bool:
    """Return whether authentication can already supply request headers."""
    try:
        _ = auth.auth_headers
    except ValueError:
        return False
    return True


def can_login(auth: AuthConfigBase) -> bool:
    """Return whether supplied credentials allow non-interactive authentication."""
    if has_auth_headers(auth):
        return True
    if isinstance(auth, LoginAuthConfig):
        return bool(auth.username and auth.password)
    if isinstance(auth, OAuth2AuthConfig):
        if auth.grant_type == "client_credentials":
            return bool(auth.client_id and auth.client_secret)
        return bool(auth.refresh_token or (auth.username and auth.password))
    if isinstance(auth, OidcAuthConfig):
        return bool(auth.refresh_token)
    return False


def _require_login() -> None:
    raise LoginRequiredError(
        "Authentication requires login. Call client.login() (await it for "
        "AsyncClient), or use 'cuiman login', to provide credentials."
    )


def _apply_tokens(auth: AuthConfigBase, tokens: TokenResult) -> None:
    values = {"access_token": tokens.access_token}
    if tokens.refresh_token and (
        isinstance(auth, OidcAuthConfig)
        or (isinstance(auth, OAuth2AuthConfig) and auth.grant_type == "password")
    ):
        values["refresh_token"] = tokens.refresh_token
    _commit_secrets(auth, values)


def _commit_secrets(auth: AuthConfigBase, values: Mapping[str, str | None]) -> None:
    # Save first: failed persistence must not publish a partially updated session.
    candidate = auth.model_copy(update=values)
    candidate.persist_secrets()
    for name, value in values.items():
        setattr(auth, name, value)


def _without_tokens(auth: AuthConfigBase) -> AuthConfigBase:
    # A fresh candidate has no persistence hook and cannot alter live secrets.
    values = auth.model_dump()
    for name in ("access_token", "refresh_token"):
        if name in values:
            values[name] = None
    return type(auth)(**values)


def _commit_auth(auth: AuthConfigBase, candidate: AuthConfigBase) -> None:
    # Include missing secrets so a fresh login cannot retain an old token.
    _commit_secrets(
        auth, {name: getattr(candidate, name) for name in auth.secret_fields}
    )


def _recover_refresh(
    auth: AuthConfigBase, error: httpx2.HTTPStatusError
) -> AuthConfigBase:
    is_refresh = (
        isinstance(auth, OidcAuthConfig)
        or isinstance(auth, OAuth2AuthConfig)
        and auth.grant_type == "password"
    ) and bool(getattr(auth, "refresh_token", None))
    if not is_refresh or error.response.status_code != 400:
        raise error
    try:
        detail = error.response.json()
    except ValueError:
        raise error from None
    if not isinstance(detail, dict) or detail.get("error") != "invalid_grant":
        raise error
    if isinstance(auth, OAuth2AuthConfig) and auth.username and auth.password:
        return _without_tokens(auth)
    raise LoginRequiredError(
        "The refresh token is no longer valid. Call client.login(force=True) "
        "(await it for AsyncClient), or use 'cuiman login', to sign in again."
    ) from error


def _obtain_tokens(
    auth: LoginAuthConfig | OAuth2AuthConfig | OidcAuthConfig,
) -> TokenResult:
    if isinstance(auth, LoginAuthConfig):
        return login(auth)
    if isinstance(auth, OAuth2AuthConfig):
        return (
            renew_oauth2_tokens(auth)
            if auth.grant_type == "password" and auth.refresh_token
            else obtain_oauth2_tokens(auth)
        )
    return renew_oidc_tokens(auth)


async def _obtain_tokens_async(
    auth: LoginAuthConfig | OAuth2AuthConfig | OidcAuthConfig,
) -> TokenResult:
    if isinstance(auth, LoginAuthConfig):
        return await login_async(auth)
    if isinstance(auth, OAuth2AuthConfig):
        return (
            await renew_oauth2_tokens_async(auth)
            if auth.grant_type == "password" and auth.refresh_token
            else await obtain_oauth2_tokens_async(auth)
        )
    return await renew_oidc_tokens_async(auth)


def make_token_refresher(
    auth: AuthConfigBase,
) -> Callable[[], dict[str, str]] | None:
    """Bind non-interactive renewal for OAuth2 and OIDC configurations.

    Static tokens and proprietary login retain their existing no-renewal policy.
    Both initial acquisition and renewal use the same token commit operation.
    """
    if isinstance(auth, (OAuth2AuthConfig, OidcAuthConfig)):
        return partial(_refresh_auth_headers, auth)
    return None


def make_async_token_refresher(
    auth: AuthConfigBase,
) -> Callable[[], Awaitable[dict[str, str]]] | None:
    """Bind asynchronous non-interactive renewal when supported."""
    if isinstance(auth, (OAuth2AuthConfig, OidcAuthConfig)):
        return partial(_refresh_auth_headers_async, auth)
    return None


def _refresh_auth_headers(
    auth: LoginAuthConfig | OAuth2AuthConfig | OidcAuthConfig,
) -> dict[str, str]:
    try:
        tokens = _obtain_tokens(auth)
    except httpx2.HTTPStatusError as error:
        candidate = _recover_refresh(auth, error)
        resolve_auth_headers(candidate)
        _commit_auth(auth, candidate)
    else:
        _apply_tokens(auth, tokens)
    return dict(auth.auth_headers)


async def _refresh_auth_headers_async(
    auth: LoginAuthConfig | OAuth2AuthConfig | OidcAuthConfig,
) -> dict[str, str]:
    try:
        tokens = await _obtain_tokens_async(auth)
    except httpx2.HTTPStatusError as error:
        candidate = _recover_refresh(auth, error)
        await resolve_auth_headers_async(candidate)
        _commit_auth(auth, candidate)
    else:
        _apply_tokens(auth, tokens)
    return dict(auth.auth_headers)


def resolve_auth_headers(
    auth: AuthConfigBase,
    *,
    interactive: bool = False,
    no_browser: bool = False,
    force: bool = False,
) -> dict[str, str]:
    """Prepare authentication, optionally bypassing existing tokens.

    Forced login uses available credentials or, when allowed, interaction.
    Existing secrets remain unchanged until new authentication is saved.
    """
    if force:
        candidate = _without_tokens(auth)
        resolve_auth_headers(candidate, interactive=interactive, no_browser=no_browser)
        _commit_auth(auth, candidate)
        return dict(auth.auth_headers)
    if has_auth_headers(auth):
        return dict(auth.auth_headers)
    if not can_login(auth):
        if not interactive:
            _require_login()
        from .interactive import prompt_auth

        candidate = prompt_auth(auth, no_browser=no_browser)
        resolve_auth_headers(candidate)
        _commit_secrets(auth, candidate.to_secret_dict())
    elif isinstance(auth, (LoginAuthConfig, OAuth2AuthConfig, OidcAuthConfig)):
        return _refresh_auth_headers(auth)
    return dict(auth.auth_headers)


async def resolve_auth_headers_async(
    auth: AuthConfigBase,
    *,
    interactive: bool = False,
    no_browser: bool = False,
    force: bool = False,
) -> dict[str, str]:
    """Prepare authentication asynchronously, optionally bypassing tokens."""
    if force:
        candidate = _without_tokens(auth)
        await resolve_auth_headers_async(
            candidate, interactive=interactive, no_browser=no_browser
        )
        _commit_auth(auth, candidate)
        return dict(auth.auth_headers)
    if has_auth_headers(auth):
        return dict(auth.auth_headers)
    if not can_login(auth):
        if not interactive:
            _require_login()
        from .interactive import prompt_auth_async

        candidate = await prompt_auth_async(auth, no_browser=no_browser)
        await resolve_auth_headers_async(candidate)
        _commit_secrets(auth, candidate.to_secret_dict())
    elif isinstance(auth, (LoginAuthConfig, OAuth2AuthConfig, OidcAuthConfig)):
        return await _refresh_auth_headers_async(auth)
    return dict(auth.auth_headers)
