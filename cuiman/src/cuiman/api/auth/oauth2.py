#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import httpx

from .config import OAuth2AuthConfig
from .login import TokenResult


def obtain_oauth2_tokens(auth_config: OAuth2AuthConfig) -> TokenResult:
    """Obtain OAuth2 tokens using the configured grant."""
    url, data = prepare_oauth2_token_request(auth_config)
    with httpx.Client() as client:
        response = client.post(url, data=data)
        return process_oauth2_token_response(response)


def renew_oauth2_tokens(auth_config: OAuth2AuthConfig) -> TokenResult:
    """Refresh or reacquire OAuth2 tokens according to the configured grant."""
    url, data = prepare_oauth2_renewal_request(auth_config)
    with httpx.Client() as client:
        response = client.post(url, data=data)
        return process_oauth2_token_response(response)


def prepare_oauth2_token_request(
    config: OAuth2AuthConfig,
) -> tuple[str, dict[str, str]]:
    """Build an OAuth2 token request for the configured grant."""
    data: dict[str, str] = {"grant_type": config.grant_type}
    if config.grant_type == "password":
        assert config.username is not None
        assert config.password is not None
        data.update(username=config.username, password=config.password)
    _add_client_credentials(config, data)
    return str(config.token_url), data


def prepare_oauth2_renewal_request(
    config: OAuth2AuthConfig,
) -> tuple[str, dict[str, str]]:
    """Build a grant-aware OAuth2 token renewal request."""
    if config.grant_type == "password" and config.refresh_token:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": config.refresh_token,
        }
        _add_client_credentials(config, data)
        return str(config.token_url), data
    return prepare_oauth2_token_request(config)


def _add_client_credentials(config: OAuth2AuthConfig, data: dict[str, str]) -> None:
    if config.client_id:
        data["client_id"] = config.client_id
    if config.client_secret:
        data["client_secret"] = config.client_secret


def process_oauth2_token_response(response: httpx.Response) -> TokenResult:
    """Parse a standards-based OAuth2 token response."""
    response.raise_for_status()
    token_data: Any = response.json()
    if not isinstance(token_data, dict):
        raise RuntimeError("OAuth2 token response must be a JSON object.")
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError(
            "OAuth2 token response must contain a non-empty string access_token."
        )
    if refresh_token is not None and not isinstance(refresh_token, str):
        raise RuntimeError("OAuth2 refresh_token must be a string when present.")
    return TokenResult(access_token=access_token, refresh_token=refresh_token)
