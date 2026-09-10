# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Configuration and storage adapters for direct Authlib HTTPX2 clients."""

import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..exceptions import ClientWarning
from .config import AuthConfigBase, OAuth2AuthConfig, OAuthTokenConfig, OidcAuthConfig
from .secret_store import SecretStoreError, save_auth_secrets


class LoginRequiredError(ValueError):
    """Credentials or an explicit interactive login are required."""


class CredentialStorageWarning(ClientWarning):
    """Live credentials remain usable, but could not be saved."""


def oauth_options(auth: OAuthTokenConfig) -> dict[str, Any]:
    """Translate provider settings to Authlib's native constructor arguments."""
    if isinstance(auth, OAuth2AuthConfig):
        options = dict(
            client_id=auth.client_id,
            client_secret=auth.client_secret,
            token_endpoint=str(auth.token_url),
            token_endpoint_auth_method="client_secret_post"
            if auth.client_secret
            else "none",
            grant_type=auth.grant_type,
        )
    else:
        assert isinstance(auth, OidcAuthConfig)
        options = dict(
            client_id=auth.client_id,
            scope=" ".join(auth.scopes),
            token_endpoint_auth_method="none",  # noqa: S106
            revocation_endpoint_auth_method="none",
            code_challenge_method="S256",
            grant_type="authorization_code",
        )
    return {**options, "token": deepcopy(auth.oauth_token)}


def save_credentials(
    auth: AuthConfigBase,
    token: dict[str, Any] | None,
    *,
    config_path: Path | None = None,
    api_url: str = "",
) -> None:
    """Persist a snapshot; optional storage failure does not invalidate live auth."""
    candidate = (
        auth.model_copy(update={"oauth_token": deepcopy(token)})
        if isinstance(auth, OAuthTokenConfig)
        else auth
    )
    if config_path is not None:
        save_auth_secrets(
            config_path, api_url, candidate.auth_type, candidate.to_secret_dict()
        )
        return
    try:
        candidate.persist_secrets()
    except SecretStoreError:
        warnings.warn(
            "Credentials are active, but saving could not be confirmed. Restarting may require login.",
            CredentialStorageWarning,
            stacklevel=2,
        )
