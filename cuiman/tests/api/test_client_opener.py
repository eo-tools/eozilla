#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from cuiman.api.client import Client
from cuiman.api.async_client import AsyncClient
from cuiman.api.opener import JobResultStatusError
from gavicore.models import (
    JobInfo,
    JobResults,
    JobStatus,
    JobType,
    Link,
    ProcessDescription,
)

from ..helpers import AllOpener


def mk_job_info(status: JobStatus, message: str | None = None):
    return JobInfo(
        jobID="job_12",
        processID="test",
        type=JobType.process,
        status=status,
        message=message,
    )


def mk_job_infos(*statuses: JobStatus):
    return [
        mk_job_info(status[0], status[1])
        if isinstance(status, tuple)
        else mk_job_info(status)
        for status in statuses
    ]


def mk_job_results():
    return JobResults(
        root={"dataset": Link(href="s3://cubes/cube.zarr", type="application/zarr")}
    )


def mk_process_description():
    return ProcessDescription(id="test", version="0.0.0")


successful_run = [JobStatus.accepted, JobStatus.running, JobStatus.successful]
failed_run = [
    JobStatus.accepted,
    JobStatus.running,
    (JobStatus.failed, "out of memory"),
]
endless_run = [JobStatus.accepted] + 100 * [JobStatus.running]


class ClientOpenJobResultTest(TestCase):
    @patch.object(Client, "get_job", side_effect=mk_job_infos(*successful_run))
    @patch.object(Client, "get_job_results", return_value=mk_job_results())
    @patch.object(Client, "get_process", return_value=mk_process_description)
    def test_successful_run(
        self,
        _get_job: MagicMock,
        _get_job_results: MagicMock,
        _get_process: MagicMock,
    ):
        client = Client(api_url="https://acme.ogc.org/api")
        client.config.opener_registry.register(AllOpener())
        result = client.open_job_result("job_12", timeout=30, poll_interval=0.01)
        self.assertIsInstance(result, JobResults)

    @patch.object(Client, "get_job", side_effect=mk_job_infos(*failed_run))
    @patch.object(Client, "get_job_results", return_value=mk_job_results())
    @patch.object(Client, "get_process", return_value=mk_process_description)
    def test_failed_run(
        self,
        _get_job: MagicMock,
        _get_job_results: MagicMock,
        _get_process: MagicMock,
    ):
        client = Client(api_url="https://acme.ogc.org/api")
        client.config.opener_registry.register(AllOpener())
        with pytest.raises(
            JobResultStatusError,
            match=(
                r"Cannot open results of job \#job_12 "
                r"because the job status is 'failed': out of memory"
            ),
        ):
            client.open_job_result("job_12", timeout=30, poll_interval=0.01)

    @patch.object(Client, "get_job", side_effect=mk_job_infos(*endless_run))
    @patch.object(Client, "get_job_results", return_value=mk_job_results())
    @patch.object(Client, "get_process", return_value=mk_process_description)
    def test_endless_run(
        self,
        _get_job: MagicMock,
        _get_job_results: MagicMock,
        _get_process: MagicMock,
    ):
        timeout = 0.1  # 100 milliseconds
        poll_interval = timeout / (len(endless_run) // 2)

        client = Client(api_url="https://acme.ogc.org/api")
        client.config.opener_registry.register(AllOpener())
        with pytest.raises(
            TimeoutError,
            match=(
                r"Cannot open result of job #job_12; "
                r"it did not finish within 0.1 seconds"
            ),
        ):
            client.open_job_result(
                "job_12", timeout=timeout, poll_interval=poll_interval
            )


class AsyncClientOpenJobResultTest(IsolatedAsyncioTestCase):
    @patch.object(
        AsyncClient,
        "get_job",
        side_effect=mk_job_infos(*successful_run),
        new_callable=AsyncMock,
    )
    @patch.object(
        AsyncClient,
        "get_job_results",
        return_value=mk_job_results(),
        new_callable=AsyncMock,
    )
    @patch.object(
        AsyncClient,
        "get_process",
        return_value=mk_process_description,
        new_callable=AsyncMock,
    )
    async def test_successful_run(
        self,
        _get_job: MagicMock,
        _get_job_results: MagicMock,
        _get_process: MagicMock,
    ):
        client = AsyncClient(api_url="https://acme.ogc.org/api")
        client.config.opener_registry.register(AllOpener())
        result = await client.open_job_result("job_12", timeout=30, poll_interval=0.01)
        self.assertIsInstance(result, JobResults)

    @patch.object(
        AsyncClient,
        "get_job",
        side_effect=mk_job_infos(*failed_run),
        new_callable=AsyncMock,
    )
    @patch.object(
        AsyncClient,
        "get_job_results",
        return_value=mk_job_results(),
        new_callable=AsyncMock,
    )
    @patch.object(
        AsyncClient,
        "get_process",
        return_value=mk_process_description,
        new_callable=AsyncMock,
    )
    async def test_failed_run(
        self,
        _get_job: MagicMock,
        _get_job_results: MagicMock,
        _get_process: MagicMock,
    ):
        client = AsyncClient(api_url="https://acme.ogc.org/api")
        client.config.opener_registry.register(AllOpener())
        with pytest.raises(
            JobResultStatusError,
            match=(
                r"Cannot open results of job \#job_12 "
                r"because the job status is 'failed': out of memory"
            ),
        ):
            await client.open_job_result("job_12", timeout=30, poll_interval=0.01)

    @patch.object(
        AsyncClient,
        "get_job",
        side_effect=mk_job_infos(*endless_run),
        new_callable=AsyncMock,
    )
    @patch.object(
        AsyncClient,
        "get_job_results",
        return_value=mk_job_results(),
        new_callable=AsyncMock,
    )
    @patch.object(
        AsyncClient,
        "get_process",
        return_value=mk_process_description,
        new_callable=AsyncMock,
    )
    async def test_endless_run(
        self,
        _get_job: MagicMock,
        _get_job_results: MagicMock,
        _get_process: MagicMock,
    ):
        timeout = 0.1  # 100 milliseconds
        poll_interval = timeout / (len(endless_run) // 2)

        client = AsyncClient(api_url="https://acme.ogc.org/api")
        client.config.opener_registry.register(AllOpener())
        with pytest.raises(
            TimeoutError,
            match=(
                r"Cannot open result of job #job_12; "
                r"it did not finish within 0.1 seconds"
            ),
        ):
            await client.open_job_result(
                "job_12", timeout=timeout, poll_interval=poll_interval
            )
