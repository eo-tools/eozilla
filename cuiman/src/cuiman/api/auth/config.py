#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import base64
from typing import Annotated, Awaitable, Callable, Literal, TypeAlias, get_args

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

AuthType: TypeAlias = Literal[
    "none",
    "basic",
    "token",
    "login",
    "oauth2",
    "api-key",
]
"""Authentication mechanism selected by an ``AuthConfig`` discriminator.

The allowed values select the corresponding configuration model and define how
authentication headers or credentials are obtained:

* ``"none"`` uses no authentication.
* ``"basic"`` sends the configured username and password in an HTTP Basic
  ``Authorization`` header.
* ``"token"`` uses a pre-existing access token, either as a Bearer
  ``Authorization`` header or in a configured custom header.
* ``"login"`` obtains an access token from a proprietary username/password
  login endpoint before using it like token authentication.
* ``"oauth2"`` obtains and renews access tokens through an OAuth2 token
  endpoint using either the password or client-credentials grant.
* ``"api-key"`` sends the configured API key in its configured header.
"""

OAuth2GrantType: TypeAlias = Literal["password", "client_credentials"]
"""OAuth2 grants supported by Cuiman."""

AUTH_TYPE_NAMES: tuple[str, ...] = get_args(AuthType)
"""Names of the supported authentication mechanisms."""

OAUTH2_GRANT_TYPE_NAMES: tuple[str, ...] = get_args(OAuth2GrantType)
"""Names of the supported OAuth2 grants."""


class AuthConfigBase(BaseModel):
    """Base class for authentication configuration models."""

    model_config = ConfigDict(extra="forbid")

    auth_type: AuthType

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return the HTTP authentication headers for this configuration."""
        return {}

    def make_token_refresher(self) -> Callable[[], dict[str, str]] | None:
        """Create a synchronous token refresh callback when supported."""
        return None

    def make_async_token_refresher(
        self,
    ) -> Callable[[], Awaitable[dict[str, str]]] | None:
        """Create an asynchronous token refresh callback when supported."""
        return None


class NoAuthConfig(AuthConfigBase):
    """Configuration for APIs that require no authentication."""

    auth_type: Literal["none"] = "none"


class BasicAuthConfig(AuthConfigBase):
    """HTTP Basic authentication configuration."""

    auth_type: Literal["basic"] = "basic"
    username: str
    password: str

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return an HTTP Basic Authorization header."""
        if not self.username or not self.password:
            raise ValueError("username/password required for basic authentication.")
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}


class _AccessTokenAuthConfig(AuthConfigBase):
    access_token: str | None = None
    use_bearer: bool = True
    access_token_header: str = "X-Auth-Token"  # noqa: S105

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            raise ValueError("Missing access token.")
        if self.use_bearer:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {self.access_token_header: self.access_token}


class TokenAuthConfig(_AccessTokenAuthConfig):
    """Static access-token authentication configuration."""

    auth_type: Literal["token"] = "token"
    access_token: str


class LoginAuthConfig(_AccessTokenAuthConfig):
    """Configuration for a proprietary username/password login endpoint."""

    auth_type: Literal["login"] = "login"
    login_url: HttpUrl
    username: str
    password: str


class OAuth2AuthConfig(_AccessTokenAuthConfig):
    """OAuth2 token endpoint configuration."""

    auth_type: Literal["oauth2"] = "oauth2"
    token_url: HttpUrl
    grant_type: OAuth2GrantType = "password"
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    refresh_token: str | None = None

    @model_validator(mode="after")
    def validate_grant_credentials(self) -> "OAuth2AuthConfig":
        """Validate the credentials required by the selected grant."""
        if self.grant_type == "password" and not (self.username and self.password):
            raise ValueError(
                "Username and password are required for the OAuth2 password grant."
            )
        if self.grant_type == "client_credentials" and not (
            self.client_id and self.client_secret
        ):
            raise ValueError(
                "Client ID and client secret are required for the OAuth2 "
                "client credentials grant."
            )
        return self

    def make_token_refresher(self) -> Callable[[], dict[str, str]]:
        """Create a synchronous OAuth2 token renewal callback."""

        def refresh() -> dict[str, str]:
            from .oauth2 import renew_oauth2_tokens

            result = renew_oauth2_tokens(self)
            self.access_token = result.access_token
            if self.grant_type == "password" and result.refresh_token:
                self.refresh_token = result.refresh_token
            return self.auth_headers

        return refresh

    def make_async_token_refresher(
        self,
    ) -> Callable[[], Awaitable[dict[str, str]]]:
        """Create an asynchronous OAuth2 token renewal callback."""

        async def refresh() -> dict[str, str]:
            from .oauth2_async import renew_oauth2_tokens_async

            result = await renew_oauth2_tokens_async(self)
            self.access_token = result.access_token
            if self.grant_type == "password" and result.refresh_token:
                self.refresh_token = result.refresh_token
            return self.auth_headers

        return refresh


class ApiKeyAuthConfig(AuthConfigBase):
    """API-key authentication configuration."""

    auth_type: Literal["api-key"] = "api-key"
    api_key: str
    api_key_header: str = "X-API-Key"

    @property
    def auth_headers(self) -> dict[str, str]:
        """Return the configured API-key header."""
        if not self.api_key:
            raise ValueError("api_key must be set for authentication type 'api-key'.")
        return {self.api_key_header: self.api_key}


AuthConfig: TypeAlias = Annotated[
    NoAuthConfig
    | BasicAuthConfig
    | TokenAuthConfig
    | LoginAuthConfig
    | OAuth2AuthConfig
    | ApiKeyAuthConfig,
    Field(discriminator="auth_type"),
]
"""Discriminated union of authentication configuration models."""
