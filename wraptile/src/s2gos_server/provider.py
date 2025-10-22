#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging

from s2gos_common.service import Service

from .services.base import ServiceBase


def get_service() -> Service:
    return ServiceProvider.get_instance()


class ServiceProvider:
    _service: Service | None = None

    @classmethod
    def get_instance(cls) -> Service:
        if cls._service is None:
            cls.set_instance(ServiceBase.load())
        assert cls._service is not None
        return cls._service

    @classmethod
    def set_instance(cls, service: Service):
        cls._service = service
        logger = logging.getLogger("uvicorn")
        logger.info(f"Using service instance of type {type(service).__name__}")
