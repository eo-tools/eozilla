#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase, TestCase

import fastapi
import pytest

from s2gos_common.models import (
    Capabilities,
    ConformanceDeclaration,
    JobInfo,
    JobList,
    JobResults,
    JobStatus,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from s2gos_common.process import Process
from s2gos_common.util.testing import set_env
from s2gos_server.exceptions import ServiceException
from s2gos_server.main import app
from s2gos_server.provider import ServiceProvider, get_service
from s2gos_server.services.local import LocalService


class LocalServiceSetupTest(TestCase):
    def setUp(self):
        service = LocalService(title="OGC API - Processes - Test Service")

        @service.process(id="foo", version="1.0.1")
        def foo(x: bool, y: int) -> float:
            return 2 * y if x else y / 2

        @service.process(id="bar", version="1.4.2")
        def bar(x: bool, y: int) -> float:
            return 2 * y if x else y / 2

        self.service = service

    def test_configure(self):
        self.service.configure(processes=False, max_workers=1)
        self.assertIsInstance(self.service.executor, ThreadPoolExecutor)
        self.service.configure(processes=True, max_workers=4)
        self.assertIsInstance(self.service.executor, ProcessPoolExecutor)

    def test_server_setup_ok(self):
        service = self.service

        foo_entry = service.process_registry.get("foo")
        self.assertIsInstance(foo_entry, Process)
        self.assertTrue(callable(foo_entry.function))
        foo_process = foo_entry.description
        self.assertIsInstance(foo_process, ProcessDescription)
        self.assertEqual("foo", foo_process.id)
        self.assertEqual("1.0.1", foo_process.version)

        bar_entry = service.process_registry.get("bar")
        self.assertIsInstance(bar_entry, Process)
        self.assertTrue(callable(bar_entry.function))
        bar_process = bar_entry.description
        self.assertIsInstance(bar_process, ProcessDescription)
        self.assertEqual("bar", bar_process.id)
        self.assertEqual("1.4.2", bar_process.version)


class LocalServiceTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app
        self.restore_env = set_env(
            S2GOS_SERVICE="s2gos_server.services.local.testing:service"
        )
        ServiceProvider._service = None
        self.service = get_service()
        self.assertIsInstance(self.service, LocalService)

    async def asyncTearDown(self):
        self.restore_env()

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
        process = await self.service.get_process(
            process_id="primes_between", request=self.get_request()
        )
        self.assertIsInstance(process, ProcessDescription)

    async def test_execute_process(self):
        job_info = await self.service.execute_process(
            process_id="primes_between",
            process_request=ProcessRequest(inputs=dict(min_val=10, max_val=30)),
            request=self.get_request(),
        )
        self.assertIsInstance(job_info, JobInfo)

    async def test_execute_process_fail(self):
        with pytest.raises(
            ServiceException,
            match=(
                r"400: Invalid parameterization for process 'primes_between': "
                r"1 validation error for ProcessInputs\n"
                r"min_val"
            ),
        ):
            await self.service.execute_process(
                process_id="primes_between",
                process_request=ProcessRequest(inputs=dict(min_val=-1, max_val=30)),
                request=self.get_request(),
            )

    async def test_execute_process_base_model_input(self):
        job_info = await self.service.execute_process(
            process_id="return_base_model",
            process_request=ProcessRequest(
                inputs={
                    "scene_spec": {
                        "threshold": 0.12,
                        "factor": 2,
                    },
                }
            ),
            request=self.get_request(),
        )
        self.assertIsInstance(job_info, JobInfo)

    async def test_get_jobs(self):
        job_list = await self.service.get_jobs(request=self.get_request())
        self.assertIsInstance(job_list, JobList)

    async def test_get_job(self):
        job_info_0 = await self.service.execute_process(
            process_id="primes_between",
            process_request=ProcessRequest(),
            request=self.get_request(),
        )
        job_info = await self.service.get_job(
            job_id=job_info_0.jobID, request=self.get_request()
        )
        self.assertIsInstance(job_info, JobInfo)
        self.assertEqual("primes_between", job_info.processID)
        self.assertEqual(job_info_0.jobID, job_info.jobID)

    async def test_get_job_results(self):
        job_info = await self.service.execute_process(
            process_id="primes_between",
            process_request=ProcessRequest(inputs={"max_val": 20}),
            request=self.get_request(),
        )
        job_id = job_info.jobID
        while job_info.status in (JobStatus.accepted, JobStatus.running):
            job_info = await self.service.get_job(
                job_id=job_id, request=self.get_request()
            )
        self.assertEqual(JobStatus.successful, job_info.status)
        job_results = await self.service.get_job_results(
            job_id=job_id, request=self.get_request()
        )
        self.assertIsInstance(job_results, JobResults)
        self.assertEqual(
            {"return_value": [2, 3, 5, 7, 11, 13, 17, 19]},
            job_results.model_dump(mode="python"),
        )
