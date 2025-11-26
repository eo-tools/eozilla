#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Dict

from .config import AuthConfig, AuthType


def get_auth_headers(config: AuthConfig) -> Dict[str, str]:
    """
    Returns the HTTP authentication headers for given auth type.
    """

    auth_type = config.auth_type

    if auth_type == AuthType.NONE:
        return {}

    # Static API token
    if auth_type == AuthType.TOKEN:
        if not config.token:
            raise ValueError("Token must be set for TOKEN auth strategy.")

        if config.use_bearer:
            return {"Authorization": f"Bearer {config.token}"}
        else:
            return {config.token_header: config.token}

    # Username/password login (token acquired earlier)
    if auth_type == AuthType.LOGIN:
        if not config.token:
            raise ValueError("Token is missing. Run CLI 'login' first.")
        return {config.token_header: config.token}

    # API Key header
    if auth_type == AuthType.API_KEY:
        if not config.api_key:
            raise ValueError("api_key must be set for API_KEY auth strategy.")
        return {config.api_key_header: config.api_key}

    # Basic Auth (username/password)
    if auth_type == AuthType.BASIC:
        if not (config.username and config.password):
            raise ValueError("username/password required for BASIC auth.")

        import base64

        creds = f"{config.username}:{config.password}"
        encoded = base64.b64encode(creds.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    raise NotImplementedError(f"Unknown authentication strategy: {auth_type}")
