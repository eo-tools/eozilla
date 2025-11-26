#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Dict

from .config import AuthConfig
from .strategy import AuthStrategy


def get_auth_headers(config: AuthConfig) -> Dict[str, str]:
    """
    Returns the correct HTTP authentication headers based on the configured auth strategy.
    Lightweight and fully generic.
    """

    if config.auth_strategy == AuthStrategy.NONE:
        return {}

    # Static API token
    if config.auth_strategy == AuthStrategy.TOKEN:
        if not config.token:
            raise ValueError("Token must be set for TOKEN auth strategy.")

        if config.use_bearer:
            return {"Authorization": f"Bearer {config.token}"}
        else:
            return {config.token_header: config.token}

    # Username/password login (token acquired earlier)
    if config.auth_strategy == AuthStrategy.LOGIN:
        if not config.token:
            raise ValueError("Token is missing. Run CLI `login` first.")
        return {config.token_header: config.token}

    # API Key header
    if config.auth_strategy == AuthStrategy.API_KEY:
        if not config.api_key:
            raise ValueError("api_key must be set for API_KEY auth strategy.")
        return {config.api_key_header: config.api_key}

    # Basic Auth (username/password)
    if config.auth_strategy == AuthStrategy.BASIC:
        if not (config.basic_username and config.basic_password):
            raise ValueError("basic_username/basic_password required for BASIC auth.")

        import base64

        creds = f"{config.basic_username}:{config.basic_password}"
        encoded = base64.b64encode(creds.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    raise NotImplementedError(
        f"Unknown authentication strategy: {config.auth_strategy}"
    )
