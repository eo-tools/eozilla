#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import IsolatedAsyncioTestCase

from tests.helpers import MockTransport

from s2gos_client import ClientConfig
from s2gos_client.api.async_client import AsyncClient
from s2gos_common.models import (
    Capabilities,
    ConformanceDeclaration,
    JobInfo,
    JobList,
    JobResults,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from s2gos_common.process import ExecutionRequest


class AsyncClientTest(IsolatedAsyncioTestCase):
    # noinspection PyPep8Naming
    async def asyncSetUp(self):
        self.transport = MockTransport()
        self.client = AsyncClient(_transport=self.transport)

    async def test_config(self):
        self.assertIsInstance(self.client.config, ClientConfig)

    async def test_repr_json(self):
        result = self.client._repr_json_()
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))
        data, metadata = result
        self.assertIsInstance(data, dict)
        self.assertIsInstance(metadata, dict)
        self.assertEqual({"root": "Client configuration:"}, metadata)

    async def test_create_execution_request(self):
        request = await self.client.create_execution_request(
            process_id="ID-1",
        )
        self.assertEqual(
            ExecutionRequest(process_id="ID-1", inputs={}),
            request,
        )

    async def test_create_execution_request_dotpath(self):
        request = await self.client.create_execution_request(
            process_id="ID-1", dotpath=True
        )
        self.assertEqual(
            ExecutionRequest(process_id="ID-1", inputs={}, dotpath=True),
            request,
        )

    async def test_get_capabilities(self):
        result = await self.client.get_capabilities()
        self.assertIsInstance(result, Capabilities)

    async def test_get_conformance(self):
        result = await self.client.get_conformance()
        self.assertIsInstance(result, ConformanceDeclaration)

    async def test_get_processes(self):
        result = await self.client.get_processes()
        self.assertIsInstance(result, ProcessList)

    async def test_get_process(self):
        result = await self.client.get_process(process_id="gobabeb_1")
        self.assertIsInstance(result, ProcessDescription)

    async def test_execute_process(self):
        result = await self.client.execute_process(
            process_id="gobabeb_1",
            request=ProcessRequest(
                inputs={"bbox": [10, 20, 30, 40]},
                outputs={},
            ),
        )
        self.assertIsInstance(result, JobInfo)

    async def test_get_jobs(self):
        result = await self.client.get_jobs()
        self.assertIsInstance(result, JobList)

    async def test_dismiss_job(self):
        result = await self.client.dismiss_job("job_12")
        self.assertIsInstance(result, JobInfo)

    async def test_get_job(self):
        result = await self.client.get_job("job_12")
        self.assertIsInstance(result, JobInfo)

    async def test_get_job_results(self):
        result = await self.client.get_job_results("job_12")
        self.assertIsInstance(result, JobResults)

    async def test_close(self):
        self.assertFalse(self.transport.closed)
        await self.client.close()
        self.assertTrue(self.transport.closed)
