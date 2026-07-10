#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Literal

from pydantic import BaseModel

from cuiman.api.config import AuthConfig, ClientConfig

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


_AUTH_TYPE_TO_APPLICABLE_KEYS: dict[str, tuple[str, ...]] = {
    "none": ("auth_type",),
    "basic": ("auth_type", "auth_url", "username", "password"),
    "login": (
        "auth_type",
        "auth_url",
        "username",
        "password",
        "token",
        "use_bearer",
        "token_header",
        "refresh_token",
        "client_id",
        "client_secret",
        "grant_type",
    ),
    "token": (
        "auth_type",
        "auth_url",
        "token",
        "use_bearer",
        "token_header",
        "refresh_token",
    ),
    "api-key": ("auth_type", "auth_url", "api_key", "api_key_header"),
}


def _config_to_service_options(client_config: ClientConfig) -> dict[str, Any]:
    """
    Convert a ClientConfig object to a JSON-serializable dict, which includes
    only keywords applicable to the given ``auth_config.auth_type``.
    """
    auth_keys = set(AuthConfig.model_fields.keys())
    applicable_auth_keys = _AUTH_TYPE_TO_APPLICABLE_KEYS[
        client_config.auth_type or "none"
    ]
    auth_config_dict = {
        k: v
        for k, v in client_config.model_dump(
            mode="json",
            exclude_none=True,
        ).items()
        if k not in auth_keys or k in applicable_auth_keys
    }
    # Additional cleanup
    if "token_header" in auth_config_dict and client_config.use_bearer:
        del auth_config_dict["token_header"]
    return {_snake_to_camel(k): v for k, v in auth_config_dict.items()}


def _snake_to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])
