#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Shared preparation of authentication for clients, app launches, and the CLI."""

from .config import AuthConfigBase, LoginAuthConfig, OAuth2AuthConfig, OidcAuthConfig
from .login import TokenResult, login
from .login_async import login_async
from .oauth2 import obtain_oauth2_tokens, renew_oauth2_tokens
from .oauth2_async import obtain_oauth2_tokens_async, renew_oauth2_tokens_async
from .oidc import renew_oidc_tokens
from .oidc_async import renew_oidc_tokens_async


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
    if "refresh_token" in auth.secret_fields and tokens.refresh_token is not None:
        values["refresh_token"] = tokens.refresh_token
    _commit_secrets(auth, values)


def _commit_secrets(auth: AuthConfigBase, values: dict[str, str]) -> None:
    # Save first: a failed secret-store write must leave login retryable.
    candidate = auth.model_copy(update=values)
    candidate.persist_secrets()
    for name, value in values.items():
        setattr(auth, name, value)


def resolve_auth_headers(
    auth: AuthConfigBase, *, interactive: bool = False, no_browser: bool = False
) -> dict[str, str]:
    """Prepare authentication, prompting only when explicitly allowed."""
    if has_auth_headers(auth):
        return dict(auth.auth_headers)
    if not can_login(auth):
        if not interactive:
            _require_login()
        from .interactive import prompt_auth

        candidate = prompt_auth(auth, no_browser=no_browser)
        resolve_auth_headers(candidate)
        _commit_secrets(auth, candidate.to_secret_dict())
    elif isinstance(auth, LoginAuthConfig):
        _apply_tokens(auth, login(auth))
    elif isinstance(auth, OAuth2AuthConfig):
        tokens = (
            renew_oauth2_tokens(auth)
            if auth.grant_type == "password" and auth.refresh_token
            else obtain_oauth2_tokens(auth)
        )
        _apply_tokens(auth, tokens)
    elif isinstance(auth, OidcAuthConfig):
        _apply_tokens(auth, renew_oidc_tokens(auth))
    return dict(auth.auth_headers)


async def resolve_auth_headers_async(
    auth: AuthConfigBase, *, interactive: bool = False, no_browser: bool = False
) -> dict[str, str]:
    """Prepare authentication without blocking asynchronous API requests."""
    if has_auth_headers(auth):
        return dict(auth.auth_headers)
    if not can_login(auth):
        if not interactive:
            _require_login()
        from .interactive import prompt_auth_async

        candidate = await prompt_auth_async(auth, no_browser=no_browser)
        await resolve_auth_headers_async(candidate)
        _commit_secrets(auth, candidate.to_secret_dict())
    elif isinstance(auth, LoginAuthConfig):
        _apply_tokens(auth, await login_async(auth))
    elif isinstance(auth, OAuth2AuthConfig):
        tokens = (
            await renew_oauth2_tokens_async(auth)
            if auth.grant_type == "password" and auth.refresh_token
            else await obtain_oauth2_tokens_async(auth)
        )
        _apply_tokens(auth, tokens)
    elif isinstance(auth, OidcAuthConfig):
        _apply_tokens(auth, await renew_oidc_tokens_async(auth))
    return dict(auth.auth_headers)
