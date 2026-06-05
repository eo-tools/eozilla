#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from gavicore.models import (
    ApiError,
    JobInfo,
    JobResults,
    JobStatus,
    ProcessDescription,
    ProcessRequest,
)
from gavicore.util.runsync import run_sync

from .config import ClientConfig
from .defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from .exceptions import ClientError
from .opener import JobResultOpenContext
from .opener.opener import open_job_result

JobUpdateHandler = Callable[[JobInfo], Awaitable[None] | None]


class JobMonitor:
    """Monitor job status updates and request cancellation.

    The generated asynchronous service clients accept a monitor through
    [JobOptions][cuiman.api.jobs.JobOptions]. The monitor stores the latest
    observed job information, forwards updates to an optional handler, and lets
    callers request job cancellation.
    """

    def __init__(self, on_update: JobUpdateHandler | None = None):
        self._on_update = on_update
        self._latest: JobInfo | None = None
        self._cancellation_requested = False

    @property
    def latest(self) -> JobInfo | None:
        """The latest observed job status information."""
        return self._latest

    @property
    def cancellation_requested(self) -> bool:
        """Whether job cancellation has been requested."""
        return self._cancellation_requested

    def cancel(self) -> None:
        """Request cancellation of the monitored job."""
        self._cancellation_requested = True

    async def update(self, job_info: JobInfo) -> None:
        """Record and publish a job status update."""
        self._latest = job_info
        if self._on_update is None:
            return
        result = self._on_update(job_info)
        if inspect.isawaitable(result):
            await result


@dataclass(frozen=True)
class JobOptions:
    """Options for generated service-client job execution."""

    output_name: str | None = None
    """Name of the output to open. If omitted, the opener chooses."""

    data_type: type | None = None
    """Expected or desired data type of the opened result."""

    media_type: str | None = None
    """Media type override used when opening the job result."""

    poll_interval: float = DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL
    """Interval in seconds between status polls."""

    timeout: float = DEFAULT_OPEN_JOB_RESULT_TIMEOUT
    """Maximum time in seconds to wait for job completion."""

    monitor: JobMonitor | None = None
    """Optional monitor for updates and cancellation requests."""

    opener_options: dict[str, Any] = field(default_factory=dict)
    """Additional opener-specific options."""


class _ClientLike(Protocol):
    @property
    def config(self) -> ClientConfig: ...

    def execute_process(self, process_id: str, request: ProcessRequest) -> JobInfo: ...

    def get_job(self, job_id: str) -> JobInfo: ...

    def dismiss_job(self, job_id: str) -> JobInfo: ...

    def get_job_results(self, job_id: str) -> JobResults: ...

    def get_process(self, process_id: str) -> ProcessDescription: ...


class _AsyncClientLike(Protocol):
    @property
    def config(self) -> ClientConfig: ...

    async def execute_process(
        self, process_id: str, request: ProcessRequest
    ) -> JobInfo: ...

    async def get_job(self, job_id: str) -> JobInfo: ...

    async def dismiss_job(self, job_id: str) -> JobInfo: ...

    async def get_job_results(self, job_id: str) -> JobResults: ...

    async def get_process(self, process_id: str) -> ProcessDescription: ...


def execute_and_open_result(
    client: _ClientLike,
    process_id: str,
    request: ProcessRequest,
    *,
    job_options: JobOptions | None = None,
) -> Any:
    """Execute a process, wait for completion, and open its result."""
    options = job_options or JobOptions()
    job_info = client.execute_process(process_id, request)
    _monitor_update_sync(options.monitor, job_info)
    job_info = _wait_for_job(client, job_info, options)
    return _open_finished_job_result(client, job_info, options)


async def async_execute_and_open_result(
    client: _AsyncClientLike,
    process_id: str,
    request: ProcessRequest,
    *,
    job_options: JobOptions | None = None,
) -> Any:
    """Execute a process asynchronously, wait for completion, and open its result."""
    options = job_options or JobOptions()
    job_info = await client.execute_process(process_id, request)
    await _monitor_update_async(options.monitor, job_info)
    job_info = await _async_wait_for_job(client, job_info, options)
    return await _async_open_finished_job_result(client, job_info, options)


def _wait_for_job(
    client: _ClientLike, job_info: JobInfo, options: JobOptions
) -> JobInfo:
    deadline = time.monotonic() + options.timeout
    while job_info.status in (JobStatus.accepted, JobStatus.running):
        if options.monitor and options.monitor.cancellation_requested:
            dismissed_job_info = client.dismiss_job(job_info.jobID)
            _monitor_update_sync(options.monitor, dismissed_job_info)
            raise _job_cancelled_error(dismissed_job_info)
        if time.monotonic() >= deadline:
            raise _job_timeout_error(job_info, options.timeout)
        time.sleep(options.poll_interval)
        job_info = client.get_job(job_info.jobID)
        _monitor_update_sync(options.monitor, job_info)
    _ensure_successful_job(job_info)
    return job_info


async def _async_wait_for_job(
    client: _AsyncClientLike, job_info: JobInfo, options: JobOptions
) -> JobInfo:
    deadline = asyncio.get_running_loop().time() + options.timeout
    while job_info.status in (JobStatus.accepted, JobStatus.running):
        if options.monitor and options.monitor.cancellation_requested:
            dismissed_job_info = await client.dismiss_job(job_info.jobID)
            await _monitor_update_async(options.monitor, dismissed_job_info)
            raise _job_cancelled_error(dismissed_job_info)
        if asyncio.get_running_loop().time() >= deadline:
            raise _job_timeout_error(job_info, options.timeout)
        await asyncio.sleep(options.poll_interval)
        job_info = await client.get_job(job_info.jobID)
        await _monitor_update_async(options.monitor, job_info)
    _ensure_successful_job(job_info)
    return job_info


def _open_finished_job_result(
    client: _ClientLike, job_info: JobInfo, options: JobOptions
) -> Any:
    job_results = client.get_job_results(job_info.jobID)
    process_description = (
        client.get_process(job_info.processID) if job_info.processID else None
    )
    ctx = _new_open_context(
        client, job_info, job_results, options, process_description
    )
    opener_registry = client.config.get_job_result_opener_registry()
    return run_sync(open_job_result, ctx, *opener_registry.opener_types)


async def _async_open_finished_job_result(
    client: _AsyncClientLike, job_info: JobInfo, options: JobOptions
) -> Any:
    job_results = await client.get_job_results(job_info.jobID)
    process_description = (
        (await client.get_process(job_info.processID)) if job_info.processID else None
    )
    ctx = _new_open_context(
        client, job_info, job_results, options, process_description
    )
    opener_registry = client.config.get_job_result_opener_registry()
    return await open_job_result(ctx, *opener_registry.opener_types)


def _new_open_context(
    client: _ClientLike | _AsyncClientLike,
    job_info: JobInfo,
    job_results: JobResults,
    options: JobOptions,
    process_description: ProcessDescription | None,
) -> JobResultOpenContext:
    return JobResultOpenContext(
        config=client.config,
        job_id=job_info.jobID,
        job_results=job_results,
        process_description=process_description,
        output_name=options.output_name,
        data_type=options.data_type,
        _media_type=options.media_type,
        options=options.opener_options,
    )


def _monitor_update_sync(monitor: JobMonitor | None, job_info: JobInfo) -> None:
    if monitor is not None:
        run_sync(monitor.update, job_info)


async def _monitor_update_async(
    monitor: JobMonitor | None, job_info: JobInfo
) -> None:
    if monitor is not None:
        await monitor.update(job_info)


def _ensure_successful_job(job_info: JobInfo) -> None:
    if job_info.status == JobStatus.successful:
        return
    raise _job_status_error(job_info)


def _job_status_error(job_info: JobInfo) -> ClientError:
    status = 499 if job_info.status == JobStatus.dismissed else 500
    return _new_client_error(
        f"Cannot open results of job #{job_info.jobID} "
        f"because the job status is '{job_info.status.value}'",
        type_=f"urn:eozilla:job-{job_info.status.value}",
        title="Job did not complete successfully",
        status=status,
        detail=job_info.message,
    )


def _job_timeout_error(job_info: JobInfo, timeout: float) -> ClientError:
    return _new_client_error(
        f"Cannot open result of job #{job_info.jobID}; "
        f"it did not finish within {timeout} seconds",
        type_="urn:eozilla:job-timeout",
        title="Job timed out",
        status=408,
        detail=job_info.message,
    )


def _job_cancelled_error(job_info: JobInfo) -> ClientError:
    return _new_client_error(
        f"Job #{job_info.jobID} was cancelled",
        type_="urn:eozilla:job-cancelled",
        title="Job cancelled",
        status=499,
        detail=job_info.message,
    )


def _new_client_error(
    message: str,
    *,
    type_: str,
    title: str,
    status: int,
    detail: str | None = None,
) -> ClientError:
    return ClientError(
        message,
        ApiError(type=type_, title=title, status=status, detail=detail),
    )
