#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Literal, Optional, TypeAlias, get_args

from pydantic_settings import BaseSettings

AuthType: TypeAlias = Literal[
    # No authentication required
    "none",
    # HTTP Basic Auth.
    "basic",
    # Static token (X-Auth-Token or Bearer)
    "token",
    # username/password (X-Auth-Token or Bearer)
    "login",
    # X-API-Key.
    "api-key",
]

AUTH_TYPE_NAMES: tuple[str, ...] = get_args(AuthType)

# TODO: enhance AuthConfig by adding Annotated[Optional[type], Field(info)] = None
#  with info containing metadata and validation info

# TODO: make all fields optional (even bool),
#  do not use default values other than None,
#  define default values in defaults module and use
#  when required by auth_type only.


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    # Authentication type
    auth_type: Optional[AuthType] = None

    # Authentication URL, usually an endpoint ending with "/auth/login".
    auth_url: Optional[str] = None

    # For type "basic" or "login" (username/password -> token)
    username: Optional[str] = None
    password: Optional[str] = None

    # For type "token" or "login"
    token: Optional[str] = None

    # For type "token": custom header or Bearer
    use_bearer: bool = False  # if True → Authorization: Bearer <token>
    token_header: str = "X-Auth-Token"

    # For type "api-key"
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"

    @property
    def auth_headers(self) -> dict[str, str]:
        """
        Return the HTTP authentication headers for this auth configuration.
        """
        return get_auth_headers(self)


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
