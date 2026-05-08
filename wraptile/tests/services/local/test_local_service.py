#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import os
from concurrent.futures import Future
from concurrent.futures.process import ProcessPoolExecutor
from concurrent.futures.thread import ThreadPoolExecutor
from unittest import IsolatedAsyncioTestCase, TestCase

import fastapi
import pytest

from gavicore.models import (
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
from gavicore.util.testing import set_env
from procodile import Job, Process
from wraptile.exceptions import ServiceException
from wraptile.main import app
from wraptile.provider import ServiceProvider, get_service
from wraptile.services.local import LocalService
from wraptile.services.local.local_service import _run_imported_job


class LocalServiceSetupTest(TestCase):
    def setUp(self):
        service = LocalService(title="OGC API - Processes - Test Service")
        registry = service.process_registry

        @registry.main(id="foo", version="1.0.1")
        def foo(x: bool, y: int) -> float:
            return 2 * y if x else y / 2

        @registry.main(id="bar", version="1.4.2")
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


# noinspection PyMethodMayBeStatic
class LocalServiceTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app
        self.restore_env = set_env(
            EOZILLA_SERVICE="wraptile.services.local.testing:service"
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
        self.service.job_results.pop(job_id, None)
        job_results = await self.service.get_job_results(
            job_id=job_id, request=self.get_request()
        )
        self.assertIsInstance(job_results, JobResults)
        self.assertEqual(
            {"return_value": [2, 3, 5, 7, 11, 13, 17, 19]},
            job_results.model_dump(mode="python"),
        )

    async def test_get_job_results_with_process_pool(self):
        self.service.configure(processes=True, max_workers=1)
        try:
            job_info = await self.service.execute_process(
                process_id="primes_between",
                process_request=ProcessRequest(inputs={"max_val": 20}),
                request=self.get_request(),
            )
            job_id = job_info.jobID
            for _ in range(100):
                job_info = await self.service.get_job(
                    job_id=job_id, request=self.get_request()
                )
                if job_info.status not in (JobStatus.accepted, JobStatus.running):
                    break
                await asyncio.sleep(0.05)

            self.assertEqual(JobStatus.successful, job_info.status)
            job_results = await self.service.get_job_results(
                job_id=job_id, request=self.get_request()
            )
            self.assertIsInstance(job_results, JobResults)
            self.assertEqual(
                {"return_value": [2, 3, 5, 7, 11, 13, 17, 19]},
                job_results.model_dump(mode="python"),
            )
        finally:
            self.service.configure(processes=False, max_workers=3)

    async def test_execute_process_with_process_pool_requires_service_ref(self):
        self.service.configure(processes=True, max_workers=1)
        self.service.service_ref = None
        try:
            with pytest.raises(
                ServiceException,
                match="Local process execution requires the service",
            ):
                await self.service.execute_process(
                    process_id="primes_between",
                    process_request=ProcessRequest(inputs={"max_val": 20}),
                    request=self.get_request(),
                )
        finally:
            self.service.configure(processes=False, max_workers=3)

    async def test_dismiss_running_job_cancels_future(self):
        job_info = await self.service.execute_process(
            process_id="sleep_a_while",
            process_request=ProcessRequest(inputs={"duration": 0.5}),
            request=self.get_request(),
        )
        job_info = await self.service.dismiss_job(
            job_id=job_info.jobID, request=self.get_request()
        )
        self.assertIn(
            job_info.status,
            {JobStatus.accepted, JobStatus.running, JobStatus.dismissed},
        )
        self.assertTrue(self.service.jobs[job_info.jobID].cancelled)

    async def test_dismiss_finished_job_removes_cached_state(self):
        job_info = await self.service.execute_process(
            process_id="primes_between",
            process_request=ProcessRequest(inputs={"max_val": 20}),
            request=self.get_request(),
        )
        job_id = job_info.jobID
        for _ in range(100):
            job_info = await self.service.get_job(
                job_id=job_id, request=self.get_request()
            )
            if job_info.status not in (JobStatus.accepted, JobStatus.running):
                break
            await asyncio.sleep(0.05)

        self.assertEqual(JobStatus.successful, job_info.status)
        self.service.job_results[job_id] = JobResults(return_value=[])
        self.service.job_uses_processes[job_id] = False
        await self.service.dismiss_job(job_id=job_id, request=self.get_request())
        self.assertNotIn(job_id, self.service.jobs)
        self.assertNotIn(job_id, self.service.job_results)
        self.assertNotIn(job_id, self.service.job_uses_processes)

    def test_ensure_executor_reconfigures_missing_executor(self):
        self.service.executor = None
        executor = self.service._ensure_executor()
        self.assertIsInstance(executor, ThreadPoolExecutor)

    def test_ensure_executor_reconfigures_after_fork(self):
        old_executor = self.service.executor
        self.service._executor_pid = -1
        try:
            executor = self.service._ensure_executor()
        finally:
            if old_executor is not None:
                old_executor.shutdown(wait=False, cancel_futures=True)
        self.assertIsInstance(executor, ThreadPoolExecutor)
        self.assertEqual(self.service._executor_pid, os.getpid())

    def test_update_job_from_future_ignores_removed_job(self):
        future: Future = Future()
        future.set_result(JobResults(return_value=[]))
        self.service._update_job_from_future(
            "missing_job",
            future,
            use_processes=False,
        )

    def test_update_job_from_cancelled_future_marks_job_dismissed(self):
        process = self.service.process_registry.get("primes_between")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest(inputs={"max_val": 20}), job_id="job")
        future: Future = Future()
        future.cancel()
        self.service.jobs[job.job_info.jobID] = job

        self.service._update_job_from_future(
            job.job_info.jobID,
            future,
            use_processes=False,
        )

        self.assertEqual(JobStatus.dismissed, job.job_info.status)

    def test_update_job_from_failed_future_marks_job_failed(self):
        process = self.service.process_registry.get("primes_between")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest(inputs={"max_val": 20}), job_id="job")
        future: Future = Future()
        future.set_exception(RuntimeError("boom"))
        self.service.jobs[job.job_info.jobID] = job

        self.service._update_job_from_future(
            job.job_info.jobID,
            future,
            use_processes=False,
        )

        self.assertEqual(JobStatus.failed, job.job_info.status)
        self.assertEqual("boom", job.job_info.message)

    def test_get_missing_process_fails(self):
        with pytest.raises(ServiceException, match="Process 'missing' does not exist"):
            self.service._get_process("missing")

    def test_get_missing_job_fails(self):
        with pytest.raises(ServiceException, match="Job 'missing' does not exist"):
            self.service._get_job("missing", forbidden_status_codes={})

    def test_get_forbidden_job_status_fails(self):
        process = self.service.process_registry.get("primes_between")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest(inputs={"max_val": 20}), job_id="job")
        self.service.jobs[job.job_info.jobID] = job
        with pytest.raises(ServiceException, match="Job 'job' has not started yet"):
            self.service._get_job(
                job.job_info.jobID,
                forbidden_status_codes={JobStatus.accepted: "has not started yet"},
            )

    def test_run_imported_job_returns_job_info_and_results(self):
        job_info, job_results = _run_imported_job(
            "wraptile.services.local.testing:service",
            "primes_between",
            ProcessRequest(inputs={"max_val": 20}),
            "job_imported",
        )

        self.assertEqual(JobStatus.successful, job_info.status)
        self.assertIsNotNone(job_results)
        assert job_results is not None
        self.assertEqual(
            {"return_value": [2, 3, 5, 7, 11, 13, 17, 19]},
            job_results.model_dump(mode="python"),
        )

    def test_run_imported_job_fails_for_missing_process(self):
        with pytest.raises(RuntimeError, match="Process 'missing' does not exist"):
            _run_imported_job(
                "wraptile.services.local.testing:service",
                "missing",
                ProcessRequest(),
                "job_imported",
            )
