#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import IsolatedAsyncioTestCase, TestCase

import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.exceptions import ClientError
from cuiman.api.jobs import (
    JobMonitor,
    JobOptions,
    async_execute_and_open_result,
    execute_and_open_result,
)
from gavicore.models import (
    JobInfo,
    JobResults,
    JobStatus,
    Link,
    ProcessDescription,
    ProcessRequest,
)

from ..helpers import AllOpener


def mk_job_info(status: JobStatus, message: str | None = None) -> JobInfo:
    return JobInfo(
        jobID="job_1",
        processID="process_1",
        status=status,
        message=message,
    )


def mk_job_results() -> JobResults:
    return JobResults(root={"result": Link(href="s3://bucket/result.tif")})


class FakeClient:
    def __init__(self, *statuses: JobStatus | tuple[JobStatus, str]):
        self.config = ClientConfig(api_url="https://acme.ogc.org/api")
        self.config.register_job_result_opener(AllOpener)
        self._statuses = list(statuses)
        self.dismissed = False

    def execute_process(self, process_id: str, request: ProcessRequest) -> JobInfo:
        assert process_id == "process_1"
        assert request.inputs == {"bbox": [1, 2, 3, 4]}
        return mk_job_info(JobStatus.accepted)

    def get_job(self, job_id: str) -> JobInfo:
        assert job_id == "job_1"
        status = self._statuses.pop(0)
        if isinstance(status, tuple):
            return mk_job_info(status[0], status[1])
        return mk_job_info(status)

    def dismiss_job(self, job_id: str) -> JobInfo:
        assert job_id == "job_1"
        self.dismissed = True
        return mk_job_info(JobStatus.dismissed, "cancelled by user")

    def get_job_results(self, job_id: str) -> JobResults:
        assert job_id == "job_1"
        return mk_job_results()

    def get_process(self, process_id: str) -> ProcessDescription:
        assert process_id == "process_1"
        return ProcessDescription(id=process_id, version="1.0.0")


class AsyncFakeClient(FakeClient):
    async def execute_process(
        self, process_id: str, request: ProcessRequest
    ) -> JobInfo:
        return super().execute_process(process_id, request)

    async def get_job(self, job_id: str) -> JobInfo:
        return super().get_job(job_id)

    async def dismiss_job(self, job_id: str) -> JobInfo:
        return super().dismiss_job(job_id)

    async def get_job_results(self, job_id: str) -> JobResults:
        return super().get_job_results(job_id)

    async def get_process(self, process_id: str) -> ProcessDescription:
        return super().get_process(process_id)


class ExecuteAndOpenResultTest(TestCase):
    def test_successful_job_returns_opened_result(self):
        client = FakeClient(JobStatus.running, JobStatus.successful)
        result = execute_and_open_result(
            client,
            "process_1",
            ProcessRequest(inputs={"bbox": [1, 2, 3, 4]}),
            job_options=JobOptions(poll_interval=0.01),
        )
        self.assertEqual(mk_job_results(), result)

    def test_failed_job_raises_client_error(self):
        client = FakeClient(JobStatus.running, (JobStatus.failed, "out of memory"))
        with pytest.raises(ClientError, match="job status is 'failed'") as e:
            execute_and_open_result(
                client,
                "process_1",
                ProcessRequest(inputs={"bbox": [1, 2, 3, 4]}),
                job_options=JobOptions(poll_interval=0.01),
            )
        self.assertEqual("urn:eozilla:job-failed", e.value.api_error.type)


class AsyncExecuteAndOpenResultTest(IsolatedAsyncioTestCase):
    async def test_monitor_receives_updates(self):
        updates: list[JobStatus] = []

        async def on_update(job_info: JobInfo) -> None:
            updates.append(job_info.status)

        client = AsyncFakeClient(JobStatus.running, JobStatus.successful)
        monitor = JobMonitor(on_update)
        result = await async_execute_and_open_result(
            client,
            "process_1",
            ProcessRequest(inputs={"bbox": [1, 2, 3, 4]}),
            job_options=JobOptions(poll_interval=0.01, monitor=monitor),
        )
        self.assertEqual(mk_job_results(), result)
        self.assertEqual(
            [JobStatus.accepted, JobStatus.running, JobStatus.successful],
            updates,
        )
        self.assertEqual(JobStatus.successful, monitor.latest.status)

    async def test_monitor_cancels_job(self):
        client = AsyncFakeClient(JobStatus.running)
        monitor = JobMonitor()
        monitor.cancel()
        with pytest.raises(ClientError, match="was cancelled") as e:
            await async_execute_and_open_result(
                client,
                "process_1",
                ProcessRequest(inputs={"bbox": [1, 2, 3, 4]}),
                job_options=JobOptions(poll_interval=0.01, monitor=monitor),
            )
        self.assertTrue(client.dismissed)
        self.assertEqual("urn:eozilla:job-cancelled", e.value.api_error.type)
