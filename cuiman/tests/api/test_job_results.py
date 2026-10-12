# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

import asyncio
import inspect
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cuiman import AsyncClient, Client
from cuiman.api.config import ClientConfig
from cuiman.api.exceptions import ClientError
from cuiman.api.jobs import JobMonitor
from cuiman.api.opener import JobResultStatusError
from gavicore.models.core import JobInfo, JobResults, JobStatus, Link

from ..helpers import MockTransport


class JobTransport(MockTransport):
    def __init__(self):
        super().__init__()
        self.statuses = []
        self.results = JobResults(
            root={
                "dataset": Link(href="s3://bucket/result.zarr", type="application/zarr")
            }
        )

    def _create_model_object(self, args):
        if args.path == "/jobs/{jobId}" and args.method == "get":
            status = self.statuses.pop(0)
            return JobInfo(
                jobID="job_1",
                status=status,
                progress=100 if status == JobStatus.successful else 20,
                message="status message",
            )
        if args.path == "/jobs/{jobId}" and args.method == "delete":
            return JobInfo(jobID="job_1", status=JobStatus.dismissed)
        assert args.path == "/jobs/{jobId}/results"
        return self.results


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def client(request):
    return request.param(
        api_url="https://acme.ogc.org/api",
        auth={"auth_type": "none"},
        _transport=JobTransport(),
    )


async def call(method, *args, **kwargs):
    result = method(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


def calls(client):
    transport = client._transport
    return transport.async_calls if isinstance(client, AsyncClient) else transport.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statuses",
    [
        [JobStatus.successful],
        [JobStatus.accepted, JobStatus.successful],
        [JobStatus.running, JobStatus.successful],
        [JobStatus.accepted, JobStatus.running, JobStatus.successful],
    ],
)
async def test_waits_and_returns_references_without_opening(client, statuses):
    client._transport.statuses = statuses.copy()
    updates = []
    monitor = JobMonitor(lambda job: updates.append((job.status, job.progress)))
    with patch.object(ClientConfig, "get_job_result_opener_registry") as openers:
        result = await call(
            client.get_job_results,
            "job_1",
            poll_interval=0,
            monitor=monitor,
            headers={"X-Test": "results"},
        )
    assert result is client._transport.results
    assert isinstance(result, JobResults)
    assert [status for status, _ in updates] == statuses
    assert updates[-1][1] == 100
    assert monitor.latest.status == JobStatus.successful
    assert [args.path for args in calls(client)] == (
        ["/jobs/{jobId}"] * len(statuses) + ["/jobs/{jobId}/results"]
    )
    assert all(
        args.extra_kwargs == {"headers": {"X-Test": "results"}}
        for args in calls(client)
    )
    openers.assert_not_called()


@pytest.mark.asyncio
async def test_wait_false_only_requests_results(client):
    monitor = JobMonitor(Mock())
    monitor.cancel()
    result = await call(
        client.get_job_results,
        "job_1",
        wait=False,
        timeout=0,
        poll_interval=100,
        monitor=monitor,
    )
    assert result is client._transport.results
    assert len(calls(client)) == 1
    assert calls(client)[0].path == "/jobs/{jobId}/results"
    assert calls(client)[0].extra_kwargs == {}
    assert monitor.latest is None
    monitor._on_update.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", [JobStatus.failed, JobStatus.dismissed])
@pytest.mark.parametrize("pending", [[], [JobStatus.accepted, JobStatus.running]])
async def test_unsuccessful_jobs_do_not_request_results(client, terminal, pending):
    client._transport.statuses = pending + [terminal]
    monitor = JobMonitor()
    with pytest.raises(JobResultStatusError, match=terminal.value) as error:
        await call(client.get_job_results, "job_1", poll_interval=0, monitor=monitor)
    assert error.value.job_info.message == "status message"
    assert monitor.latest is error.value.job_info
    assert len(calls(client)) == len(pending) + 1
    assert all(
        args.path == "/jobs/{jobId}" and args.method == "get" for args in calls(client)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [JobStatus.accepted, JobStatus.running])
async def test_timeout_leaves_remote_job_running(client, status):
    client._transport.statuses = [status]
    with pytest.raises(TimeoutError, match="did not finish within 0 seconds"):
        await call(client.get_job_results, "job_1", timeout=0)
    assert len(calls(client)) == 1
    assert calls(client)[0].method == "get"


@pytest.mark.asyncio
async def test_poll_sleep_is_limited_by_timeout(client):
    client._transport.statuses = [JobStatus.running]
    is_async = isinstance(client, AsyncClient)
    target = (
        "cuiman.api.jobs.asyncio.sleep" if is_async else "cuiman.api.jobs.time.sleep"
    )
    sleep = AsyncMock(wraps=asyncio.sleep) if is_async else Mock(wraps=time.sleep)
    with patch(target, sleep), pytest.raises(TimeoutError):
        await call(client.get_job_results, "job_1", timeout=0.01, poll_interval=100)
    assert len(calls(client)) == 1
    sleep.assert_called_once()
    assert 0 < sleep.call_args.args[0] <= 0.01


@pytest.mark.asyncio
async def test_async_monitor_handler_is_supported(client):
    client._transport.statuses = [JobStatus.accepted, JobStatus.successful]
    handler = AsyncMock()
    monitor = JobMonitor(handler)
    await call(client.get_job_results, "job_1", poll_interval=0, monitor=monitor)
    assert handler.await_count == 2


@pytest.mark.asyncio
async def test_open_result_does_not_poll_again_after_completion(client):
    client._transport.statuses = [JobStatus.accepted, JobStatus.successful]
    target = (
        "cuiman.api.async_client_mixin.open_job_result"
        if isinstance(client, AsyncClient)
        else "cuiman.api.client_mixin.open_job_result"
    )
    with patch(target, new_callable=AsyncMock, return_value="opened") as opener:
        result = await call(client.open_job_result, "job_1", poll_interval=0)
    assert result == "opened"
    assert [args.path for args in calls(client)] == [
        "/jobs/{jobId}",
        "/jobs/{jobId}",
        "/jobs/{jobId}/results",
    ]
    opener.assert_awaited_once()


@pytest.mark.asyncio
async def test_monitor_can_explicitly_cancel(client):
    client._transport.statuses = [JobStatus.running]
    monitor = JobMonitor(lambda _: monitor.cancel())
    with pytest.raises(ClientError, match="was cancelled"):
        await call(client.get_job_results, "job_1", monitor=monitor)
    assert [args.method for args in calls(client)] == ["get", "delete"]
    assert monitor.latest.status == JobStatus.dismissed
