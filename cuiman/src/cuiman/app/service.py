#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Literal

from pydantic import BaseModel

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
    return ServiceProvider(
        id="client",
        meta=ServiceProviderMeta(
            type="custom",
            title="Client",
            description="In-app provider",
        ),
        options={
            "apiUrl": client_config.api_url,
            "authType": client_config.auth_type,
            "authUrl": client_config.auth_url,
        },
    )
