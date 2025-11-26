#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from .config import AuthConfig


def get_auth_headers(config: AuthConfig) -> dict[str, str]:
    """
    Returns the HTTP authentication headers for given auth type.
    """

    auth_type = config.auth_type

    if auth_type is None or auth_type == "none":
        return {}

    # Static API token
    if auth_type == "token":
        if not config.token:
            raise ValueError("Missing API token.")

        if config.use_bearer:
            return {"Authorization": f"Bearer {config.token}"}
        else:
            return {config.token_header: config.token}

    # Username/password login (token acquired earlier)
    if auth_type == "login":
        if not config.token:
            raise ValueError("Token is missing. Run CLI 'login' first.")
        return {config.token_header: config.token}

    # API Key header
    if auth_type == "api-key":
        if not config.api_key:
            raise ValueError("api_key must be set for authentication type 'api-key'.")
        return {config.api_key_header: config.api_key}

    # Basic Auth (username/password)
    if auth_type == "basic":
        if not (config.username and config.password):
            raise ValueError("username/password required for basic authentication.")

        import base64

        creds = f"{config.username}:{config.password}"
        encoded = base64.b64encode(creds.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    raise NotImplementedError(f"Unknown authentication type: {auth_type}")
