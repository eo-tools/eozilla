# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Persistent Authlib clients for password and client-credentials grants.

Authlib owns tokens, expiry, reacquisition, and request signing. This module
adapts configuration, provider response compatibility, and optional persistence.
"""

import warnings
from copy import deepcopy
from functools import partial
from typing import Any, TypeVar

import httpx2
from authlib.integrations.base_client.errors import InvalidTokenError
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client

from ..exceptions import ClientWarning
from .config import OAuth2AuthConfig
from .secret_store import SecretStoreError
from .session import LoginRequiredError

_Client = TypeVar("_Client", OAuth2Client, AsyncOAuth2Client)


class CredentialStorageWarning(ClientWarning):
    """Credentials remain active, but their persistence could not be confirmed."""


def needs_token(
    auth: OAuth2AuthConfig,
    client: OAuth2Client | AsyncOAuth2Client,
    *,
    force: bool = False,
) -> bool:
    """Decide whether login needs a grant and require credentials if it does."""
    if not force and client.token:
        return False
    if not auth.client_id or not auth.client_secret:
        raise LoginRequiredError(
            "Client credentials require client_id and client_secret. "
            "Provide them through environment variables or Python configuration before client.login()."
        )
    return True


def save_token(auth: OAuth2AuthConfig, token: dict[str, Any]) -> None:
    """Save a snapshot without replacing configuration's bootstrap credentials."""
    candidate = auth.model_copy(
        update={
            "access_token": None,
            "refresh_token": None,
            "oauth_token": deepcopy(dict(token)),
        }
    )
    try:
        candidate.persist_secrets()
    except SecretStoreError:
        warnings.warn(
            "Credentials are active, but saving could not be confirmed. "
            "Restarting may require login.",
            CredentialStorageWarning,
            stacklevel=2,
        )


def create_client(auth: OAuth2AuthConfig) -> OAuth2Client:
    """Create a persistent synchronous client with optional token persistence."""

    def update_token(token: dict[str, Any], **_previous: Any) -> None:
        save_token(auth, token)

    client = (
        PasswordOAuth2Client(auth, update_token=update_token, **_options(auth))
        if auth.grant_type == "password"
        else OAuth2Client(update_token=update_token, **_options(auth))
    )
    return _configure(client, auth)


def create_async_client(auth: OAuth2AuthConfig) -> AsyncOAuth2Client:
    """Create a persistent asynchronous client with an awaitable update callback."""

    async def update_token(token: dict[str, Any], **_previous: Any) -> None:
        # The current keyring API is synchronous. Keep this small save in the
        # transition, with no cancellation point between install and persistence.
        save_token(auth, token)

    client = (
        AsyncPasswordOAuth2Client(auth, update_token=update_token, **_options(auth))
        if auth.grant_type == "password"
        else AsyncOAuth2Client(update_token=update_token, **_options(auth))
    )
    return _configure(client, auth)


def _options(auth: OAuth2AuthConfig) -> dict[str, Any]:
    token = deepcopy(auth.oauth_token or {})
    if auth.access_token:
        token = {"access_token": auth.access_token}
    if auth.grant_type == "client_credentials":
        token.pop("refresh_token", None)
    elif auth.refresh_token:
        token["refresh_token"] = auth.refresh_token
    return dict(
        client_id=auth.client_id,
        client_secret=auth.client_secret,
        token_endpoint_auth_method=(
            "client_secret_post"
            if auth.grant_type == "client_credentials" or auth.client_secret
            else "none"
            if auth.client_id
            else _no_client_auth
        ),
        token_endpoint=str(auth.token_url),
        grant_type=auth.grant_type,
        token=token or None,
    )


def _configure(client: _Client, auth: OAuth2AuthConfig) -> _Client:
    client.register_compliance_hook(
        "access_token_response",
        partial(
            _token_response, discard_refresh=auth.grant_type == "client_credentials"
        ),
    )
    if auth.grant_type == "password":
        client.register_compliance_hook("refresh_token_response", _refresh_response)
    if not auth.use_bearer:

        def custom_header(
            url: str, headers: Any, body: bytes
        ) -> tuple[str, Any, bytes]:
            headers[auth.access_token_header] = headers.pop("Authorization").split(
                " ", 1
            )[1]
            return url, headers, body

        client.register_compliance_hook("protected_request", custom_header)
    return client


def _token_response(
    response: httpx2.Response, *, discard_refresh: bool = False
) -> httpx2.Response:
    # Let Authlib parse OAuth errors; unsuccessful HTTP responses without a
    # standard error must not be installed as apparently successful tokens.
    if response.status_code >= 500:
        response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and "error" in data:
        return response
    response.raise_for_status()
    if not isinstance(data, dict):
        raise RuntimeError("OAuth2 token response must be a JSON object.")
    if not isinstance(data.get("access_token"), str) or not data["access_token"]:
        raise RuntimeError("OAuth2 token response requires a non-empty access_token.")
    # RFC 6749 client credentials do not use refresh tokens. Authlib otherwise
    # prioritizes a returned refresh token over client-credentials reacquisition.
    if discard_refresh:
        data.pop("refresh_token", None)
    else:
        refresh = data.get("refresh_token")
        if refresh is not None and not isinstance(refresh, str):
            raise RuntimeError("OAuth2 refresh_token must be a string when present.")
        if not refresh:
            data.pop("refresh_token", None)
    return httpx2.Response(response.status_code, json=data, request=response.request)


def _no_client_auth(
    client: Any, method: str, uri: str, headers: Any, body: Any
) -> tuple[str, Any, Any]:
    # Authlib's "none" adds a client_id, even when none was configured.
    return uri, headers, body


def _refresh_response(response: httpx2.Response) -> httpx2.Response:
    # Preserve the exact HTTP rejection needed for password fallback. All other
    # OAuth errors are parsed by Authlib; a fresh fetch never uses this hook.
    if response.status_code == 400:
        data = response.json()
        if isinstance(data, dict) and data.get("error") == "invalid_grant":
            raise _RejectedRefresh(
                "The refresh token was rejected.",
                request=response.request,
                response=response,
            )
    return _token_response(response)


class _RejectedRefresh(httpx2.HTTPStatusError):
    """An HTTP 400 invalid_grant response from a refresh request only."""


def _password_credentials(auth: OAuth2AuthConfig) -> dict[str, str]:
    if not auth.username or not auth.password:
        raise LoginRequiredError(
            "Password authentication requires credentials. Call client.login(force=True) "
            "(await it for AsyncClient), or use 'cuiman login', to sign in again."
        )
    return dict(username=auth.username, password=auth.password)


def _save_password_token(
    auth: OAuth2AuthConfig, candidate: OAuth2AuthConfig, token: dict[str, Any]
) -> None:
    # Publish prompted bootstrap credentials only after the grant succeeds.
    auth.username, auth.password = candidate.username, candidate.password
    save_token(auth, token)


class PasswordOAuth2Client(OAuth2Client):
    """Authlib password client with explicit login and narrow renewal fallback."""

    def __init__(self, auth_config: OAuth2AuthConfig, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_config = auth_config

    def login(self, *, force: bool = False, interactive: bool = False) -> None:
        """Reuse live tokens, refresh bootstrap credentials, or explicitly sign in."""
        if not force and self.token:
            if self.token.get("access_token"):
                save_token(self._auth_config, self.token)
            else:
                self.renew()
            return
        candidate = self._auth_config
        if interactive and not (candidate.username and candidate.password):
            from .interactive import prompt_auth

            prompted = prompt_auth(candidate)
            assert isinstance(prompted, OAuth2AuthConfig)
            candidate = prompted
        self._fetch_password(candidate)

    def _fetch_password(self, candidate: OAuth2AuthConfig) -> dict[str, Any]:
        token = self.fetch_token(**_password_credentials(candidate))
        _save_password_token(self._auth_config, candidate, token)
        return token

    def renew(self) -> dict[str, str]:
        """Renew a rejected resource token without prompting; transport replays once."""
        if self.token and self.token.get("refresh_token"):
            self.refresh_token()
        else:
            self._fetch_password(self._auth_config)
        return {}

    def refresh_token(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Delegate refresh, falling back only for HTTP 400 invalid_grant."""
        try:
            return super().refresh_token(*args, **kwargs)
        except _RejectedRefresh:
            return self._fetch_password(self._auth_config)

    def ensure_active_token(self, token: Any = None) -> bool:
        """Let Authlib decide expiry, reacquiring when no refresh token exists."""
        if not super().ensure_active_token(token):
            self._fetch_password(self._auth_config)
        return True


class AsyncPasswordOAuth2Client(AsyncOAuth2Client):
    """Asynchronous Authlib password client with the same compatibility policy."""

    def __init__(self, auth_config: OAuth2AuthConfig, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_config = auth_config

    async def login(self, *, force: bool = False, interactive: bool = False) -> None:
        """Reuse live tokens, refresh bootstrap credentials, or explicitly sign in."""
        if not force and self.token:
            if self.token.get("access_token"):
                save_token(self._auth_config, self.token)
            else:
                await self.renew()
            return
        candidate = self._auth_config
        if interactive and not (candidate.username and candidate.password):
            from .interactive import prompt_auth_async

            prompted = await prompt_auth_async(candidate)
            assert isinstance(prompted, OAuth2AuthConfig)
            candidate = prompted
        await self._fetch_password(candidate)

    async def _fetch_password(self, candidate: OAuth2AuthConfig) -> dict[str, Any]:
        token = await self.fetch_token(**_password_credentials(candidate))
        _save_password_token(self._auth_config, candidate, token)
        return token

    async def renew(self) -> dict[str, str]:
        """Renew a rejected resource token without prompting; transport replays once."""
        if self.token and self.token.get("refresh_token"):
            await self.refresh_token()
        else:
            await self._fetch_password(self._auth_config)
        return {}

    async def refresh_token(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Delegate refresh, falling back only for HTTP 400 invalid_grant."""
        try:
            return await super().refresh_token(*args, **kwargs)
        except _RejectedRefresh:
            return await self._fetch_password(self._auth_config)

    async def ensure_active_token(self, token: Any) -> None:
        """Let Authlib decide expiry, reacquiring when no refresh token exists."""
        try:
            await super().ensure_active_token(token)
        except InvalidTokenError:
            if self.token.get("refresh_token"):
                raise
            await self._fetch_password(self._auth_config)
