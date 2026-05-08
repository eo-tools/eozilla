#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import multiprocessing
import os
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from concurrent.futures.process import ProcessPoolExecutor
from typing import Optional

import fastapi
from pydantic import ValidationError

from gavicore.models import (
    JobInfo,
    JobList,
    JobResults,
    JobStatus,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
)
from gavicore.util.dynimp import import_value
from procodile import Job, Process, ProcessRegistry
from wraptile.exceptions import ServiceException
from wraptile.services.base import ServiceBase


class LocalService(ServiceBase):
    def __init__(
        self,
        title: str,
        description: Optional[str] = None,
        process_registry: ProcessRegistry | None = None,
    ):
        super().__init__(title=title, description=description)
        self.executor: Optional[ThreadPoolExecutor | ProcessPoolExecutor] = None

        self.process_registry = process_registry or ProcessRegistry()
        self.jobs: dict[str, Job] = {}
        self.job_results: dict[str, JobResults | None] = {}
        self.job_uses_processes: dict[str, bool] = {}
        self._executor_uses_processes = False
        self._executor_max_workers = 3
        self._executor_pid: int | None = None

    def configure(
        self, processes: Optional[bool] = None, max_workers: Optional[int] = None
    ):
        """
        Configure the local service.

        Args:
            processes: Whether to use processes instead of threads. Defaults to threads.
            max_workers: The maximum number of processes or threads. Defaults to 3.
        """
        num_workers: int = max_workers or 3
        use_processes = bool(processes)
        if self.executor is not None and self._executor_pid == os.getpid():
            self.executor.shutdown(wait=False, cancel_futures=True)
        self._executor_uses_processes = use_processes
        self._executor_max_workers = num_workers
        self._executor_pid = os.getpid()
        if use_processes:
            self.executor = ProcessPoolExecutor(
                max_workers=num_workers,
                mp_context=multiprocessing.get_context("spawn"),
            )
            self.logger.info(f"Using processes with max {num_workers} workers.")
        else:
            self.executor = ThreadPoolExecutor(max_workers=num_workers)
            self.logger.info(f"Using threads with max {num_workers} workers.")

    async def get_processes(self, request: fastapi.Request, **_kwargs) -> ProcessList:
        return ProcessList(
            processes=[
                ProcessSummary(
                    **p.description.model_dump(
                        mode="python",
                        exclude={"inputs", "outputs"},
                    )
                )
                for p in self.process_registry.values()
            ],
            links=[self.get_self_link(request, "get_processes")],
        )

    async def get_process(self, process_id: str, **kwargs) -> ProcessDescription:
        process = self._get_process(process_id)
        return process.description

    async def execute_process(
        self, process_id: str, process_request: ProcessRequest, **_kwargs
    ) -> JobInfo:
        process = self._get_process(process_id)
        job_id = f"job_{len(self.jobs)}"
        try:
            job = Job.create(process, process_request, job_id=job_id)
        except ValidationError as e:
            raise ServiceException(
                400,
                detail=f"Invalid parameterization for process {process_id!r}: {e}",
                exception=e,
            ) from e
        executor = self._ensure_executor()
        use_processes = isinstance(executor, ProcessPoolExecutor)
        if use_processes:
            if self.service_ref is None:
                raise ServiceException(
                    500,
                    detail=(
                        "Local process execution requires the service to be "
                        "loaded from an import reference."
                    ),
                )
        self.jobs[job_id] = job
        self.job_uses_processes[job_id] = use_processes
        if use_processes:
            assert self.service_ref is not None
            job.future = executor.submit(
                _run_imported_job,
                self.service_ref,
                process_id,
                process_request,
                job_id,
            )
        else:
            job.future = executor.submit(job.run)
        job.future.add_done_callback(
            lambda future: self._update_job_from_future(
                job_id,
                future,
                use_processes=use_processes,
            )
        )
        return job.job_info

    async def get_jobs(self, request: fastapi.Request, **_kwargs) -> JobList:
        return JobList(
            jobs=[job.job_info for job in self.jobs.values()],
            links=[self.get_self_link(request, "get_jobs")],
        )

    async def get_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        job = self._get_job(job_id, forbidden_status_codes={})
        return job.job_info

    async def dismiss_job(self, job_id: str, *args, **_kwargs) -> JobInfo:
        job = self._get_job(job_id, forbidden_status_codes={})
        if job.job_info.status in (JobStatus.accepted, JobStatus.running):
            job.cancel()
            if job.future is not None:
                job.future.cancel()
        elif job.job_info.status in (
            JobStatus.dismissed,
            JobStatus.successful,
            JobStatus.failed,
        ):
            del self.jobs[job_id]
            self.job_results.pop(job_id, None)
            self.job_uses_processes.pop(job_id, None)
        return job.job_info

    async def get_job_results(self, job_id: str, *args, **_kwargs) -> JobResults:
        job = self._get_job(
            job_id,
            forbidden_status_codes={
                JobStatus.accepted: "has not started yet",
                JobStatus.running: "is still running",
                JobStatus.dismissed: "has been cancelled",
                JobStatus.failed: "has failed",
            },
        )
        assert job.job_info.status == JobStatus.successful
        assert job.future is not None
        if job_id not in self.job_results:
            self.job_results[job_id] = self._get_job_result_from_future(
                job,
                job.future,
                use_processes=self.job_uses_processes.get(job_id, False),
            )
        job_results = self.job_results[job_id]
        assert job_results is not None
        return job_results

    def _ensure_executor(self) -> ThreadPoolExecutor | ProcessPoolExecutor:
        if self.executor is None:
            self.configure(
                processes=self._executor_uses_processes,
                max_workers=self._executor_max_workers,
            )
        elif self._executor_pid != os.getpid():
            self.logger.warning("Recreating local executor after process fork.")
            self.executor = None
            self.configure(
                processes=self._executor_uses_processes,
                max_workers=self._executor_max_workers,
            )
        assert self.executor is not None, "illegal state: no executor specified"
        return self.executor

    def _update_job_from_future(
        self,
        job_id: str,
        future: Future,
        *,
        use_processes: bool,
    ):
        job = self.jobs.get(job_id)
        if job is None:
            return
        try:
            self.job_results[job_id] = self._get_job_result_from_future(
                job, future, use_processes=use_processes
            )
        except CancelledError:
            if job.job_info.status in (JobStatus.accepted, JobStatus.running):
                job._finish_job(JobStatus.dismissed)
        except Exception as e:
            self.logger.exception(f"Execution of job {job_id!r} failed.")
            if job.job_info.status in (JobStatus.accepted, JobStatus.running):
                job._finish_job(JobStatus.failed, exception=e)

    @staticmethod
    def _get_job_result_from_future(
        job: Job,
        future: Future,
        *,
        use_processes: bool,
    ) -> JobResults | None:
        future_result = future.result()
        if use_processes:
            job_info, job_results = future_result
            job.job_info = job_info
            return job_results
        return future_result

    def _get_process(self, process_id: str) -> Process:
        process = self.process_registry.get(process_id)
        if process is None:
            raise ServiceException(404, detail=f"Process {process_id!r} does not exist")
        return process

    def _get_job(
        self, job_id: str, forbidden_status_codes: dict[JobStatus, str]
    ) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise ServiceException(404, detail=f"Job {job_id!r} does not exist")
        message = forbidden_status_codes.get(job.job_info.status)
        if message:
            raise ServiceException(403, detail=f"Job {job_id!r} {message}")
        return job


def _run_imported_job(
    service_ref: str,
    process_id: str,
    process_request: ProcessRequest,
    job_id: str,
) -> tuple[JobInfo, JobResults | None]:
    service = import_value(
        service_ref,
        type=LocalService,
        name="service",
        example="path.to.module:service",
    )
    process = service.process_registry.get(process_id)
    if process is None:
        raise RuntimeError(f"Process {process_id!r} does not exist")
    job = Job.create(process, process_request, job_id=job_id)
    job_results = job.run()
    return job.job_info, job_results
