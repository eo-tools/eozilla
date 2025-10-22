#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import unittest
import warnings
from unittest import IsolatedAsyncioTestCase

import fastapi
import requests

from gavicore.models import (
    Capabilities,
    ConformanceDeclaration,
    ProcessDescription,
    ProcessList,
)
from gavicore.util.testing import set_env
from wraptile.main import app
from wraptile.provider import ServiceProvider, get_service
from wraptile.services.airflow import DEFAULT_AIRFLOW_BASE_URL, AirflowService


def is_airflow_running(url: str, timeout: float = 1.0) -> bool:
    try:
        requests.head(url, allow_redirects=True, timeout=timeout)
        return True
    except requests.RequestException:
        return False


@unittest.skipUnless(
    is_airflow_running(DEFAULT_AIRFLOW_BASE_URL),
    reason=f"No Airflow server running on {DEFAULT_AIRFLOW_BASE_URL}",
)
class AirflowServiceTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app
        self.restore_env = set_env(
            EOZILLA_SERVICE="wraptile.services.airflow:service",
        )
        ServiceProvider._service = None
        self.service = get_service()
        self.assertIsInstance(self.service, AirflowService)
        self.service.configure()

    async def asyncTearDown(self):
        self.restore_env()
        # comment out to check generated DAGs
        # shutil.rmtree(EOZILLA_AIRFLOW_DAGS_FOLDER, ignore_errors=True)

    def get_request(self) -> fastapi.Request:
        return fastapi.Request({"type": "http", "app": self.app, "headers": {}})

    async def test_get_capabilities(self):
        caps = await self.service.get_capabilities(request=self.get_request())
        self.assertIsInstance(caps, Capabilities)

    async def test_get_conformance(self):
        conf = await self.service.get_conformance(request=self.get_request())
        self.assertIsInstance(conf, ConformanceDeclaration)

    async def test_get_processes(self):
        processes = await self.service.get_processes(request=self.get_request())
        self.assertIsInstance(processes, ProcessList)

    async def test_get_process(self):
        process_list = await self.service.get_processes(request=self.get_request())
        processes = process_list.processes
        if not processes:
            warnings.warn("Skipping test; no Airflow processes found")
            return

        process = await self.service.get_process(
            process_id=processes[0].id, request=self.get_request()
        )
        self.assertIsInstance(process, ProcessDescription)
