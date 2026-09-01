#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Literal

from pydantic import BaseModel

from cuiman.api.auth import (
    AuthConfigBase,
    LoginAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
)
from cuiman.api.config import ClientConfig

ServiceProviderType = Literal["test", "dev", "custom", "system"]
ServiceProviderOption = bool | int | float | str | None


class ServiceProviderMeta(BaseModel):
    type: ServiceProviderType
    title: str
    description: str | None = None
    disabled: bool | None = None
    hidden: bool | None = None


class ServiceProvider(BaseModel):
    id: str
    meta: ServiceProviderMeta
    options: dict[str, ServiceProviderOption] = {}


def create_app_service_provider(client_config: ClientConfig) -> ServiceProvider:
    # noinspection PyTypeChecker
    options = _config_to_service_options(client_config)
    return ServiceProvider(
        id="client",
        meta=ServiceProviderMeta(
            type="custom",
            title="Client",
            description="In-app provider",
        ),
        options=options,
    )


def _effective_app_auth(auth: AuthConfigBase) -> AuthConfigBase:
    """Convert an already-resolved login or OAuth2 config to token auth."""
    if isinstance(auth, (LoginAuthConfig, OAuth2AuthConfig)) and auth.access_token:
        return TokenAuthConfig(
            access_token=auth.access_token,
            use_bearer=auth.use_bearer,
            access_token_header=auth.access_token_header,
        )
    return auth


def _config_to_service_options(client_config: ClientConfig) -> dict[str, Any]:
    """
    Convert a ClientConfig object to a flat, JSON-serializable app config.
    """
    config_dict = client_config.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"auth"},
    )
    auth_dict = _effective_app_auth(client_config.auth).model_dump(
        mode="json",
        exclude_none=True,
    )
    if auth_dict.get("use_bearer"):
        auth_dict.pop("access_token_header", None)
    config_dict.update(auth_dict)
    return {_snake_to_camel(k): v for k, v in config_dict.items()}


def _snake_to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])
