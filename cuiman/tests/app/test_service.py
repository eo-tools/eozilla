#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from cuiman.api.config import ClientConfig
from cuiman.app.service import (
    ServiceProvider,
    ServiceProviderMeta,
    create_app_service_provider,
)


def test_create_app_service_provider():
    provider = create_app_service_provider(
        ClientConfig(
            api_url="https://process.example.test/api",
            auth_type="login",
            auth_url="https://auth.example.test/login",
        )
    )

    assert isinstance(provider, ServiceProvider)
    assert provider.id == "client"
    assert provider.meta == ServiceProviderMeta(
        type="custom",
        title="Client",
        description="In-app provider",
    )
    assert provider.options == {
        "apiUrl": "https://process.example.test/api",
        "authType": "login",
        "authUrl": "https://auth.example.test/login",
    }


def test_service_provider_models_accept_optional_metadata_and_options():
    provider = ServiceProvider(
        id="dev",
        meta=ServiceProviderMeta(
            type="dev",
            title="Development",
            disabled=False,
            hidden=True,
        ),
        options={
            "enabled": True,
            "retries": 2,
            "timeout": 3.5,
            "label": "local",
            "token": None,
        },
    )

    assert provider.model_dump() == {
        "id": "dev",
        "meta": {
            "type": "dev",
            "title": "Development",
            "description": None,
            "disabled": False,
            "hidden": True,
        },
        "options": {
            "enabled": True,
            "retries": 2,
            "timeout": 3.5,
            "label": "local",
            "token": None,
        },
    }
