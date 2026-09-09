# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Persistent Authlib clients for the client-credentials grant.

Authlib owns tokens, expiry, reacquisition, and request signing. This module
adapts configuration, provider response compatibility, and optional persistence.
"""

import warnings
from copy import deepcopy
from typing import Any, TypeVar

import httpx2
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

    return _configure(OAuth2Client(update_token=update_token, **_options(auth)), auth)


def create_async_client(auth: OAuth2AuthConfig) -> AsyncOAuth2Client:
    """Create a persistent asynchronous client with an awaitable update callback."""

    async def update_token(token: dict[str, Any], **_previous: Any) -> None:
        # The current keyring API is synchronous. Keep this small save in the
        # transition, with no cancellation point between install and persistence.
        save_token(auth, token)

    return _configure(
        AsyncOAuth2Client(update_token=update_token, **_options(auth)), auth
    )


def _options(auth: OAuth2AuthConfig) -> dict[str, Any]:
    token = deepcopy(auth.oauth_token or {})
    if auth.access_token:
        token = {"access_token": auth.access_token}
    token.pop("refresh_token", None)
    return dict(
        client_id=auth.client_id,
        client_secret=auth.client_secret,
        token_endpoint_auth_method="client_secret_post",  # noqa: S106
        token_endpoint=str(auth.token_url),
        grant_type="client_credentials",
        token=token or None,
    )


def _configure(client: _Client, auth: OAuth2AuthConfig) -> _Client:
    client.register_compliance_hook("access_token_response", _token_response)
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


def _token_response(response: httpx2.Response) -> httpx2.Response:
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
    data.pop("refresh_token", None)
    return httpx2.Response(response.status_code, json=data, request=response.request)
