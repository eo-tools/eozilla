#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.process import ProcessPoolExecutor
from typing import Callable, Optional

import fastapi
import pydantic

from s2gos_common.models import (
    JobInfo,
    JobList,
    JobResults,
    JobStatus,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
    ProcessSummary,
)
from s2gos_common.process import Job, Process, ProcessRegistry
from s2gos_server.exceptions import ServiceException
from s2gos_server.services.base import ServiceBase


class LocalService(ServiceBase):
    def __init__(
        self,
        title: str,
        description: Optional[str] = None,
        process_registry: Optional[ProcessRegistry] = None,
    ):
        super().__init__(title=title, description=description)
        self.executor: Optional[ThreadPoolExecutor | ProcessPoolExecutor] = None
        self.process_registry = process_registry or ProcessRegistry()
        self.jobs: dict[str, Job] = {}

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
        if processes:
            self.executor = ProcessPoolExecutor(max_workers=num_workers)
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
        except pydantic.ValidationError as e:
            raise ServiceException(
                400,
                detail=f"Invalid parameterization for process {process_id!r}: {e}",
                exception=e,
            )
        self.jobs[job_id] = job
        assert self.executor is not None, "illegal state: no executor specified"
        job.future = self.executor.submit(job.run)
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
        elif job.job_info.status in (
            JobStatus.dismissed,
            JobStatus.successful,
            JobStatus.failed,
        ):
            del self.jobs[job_id]
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
        return job.future.result()

    # noinspection PyShadowingBuiltins
    def process(
        self,
        function: Optional[Callable] = None,
        /,
        *,
        id: Optional[str] = None,
        version: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        input_fields: Optional[dict[str, pydantic.fields.FieldInfo]] = None,
        output_fields: Optional[dict[str, pydantic.fields.FieldInfo]] = None,
    ) -> Callable[[Callable], Callable]:
        """
        A decorator that can be applied to a user function in order to
        register it as a process in this registry.

        The decorator can be used with or without parameters.
        """
        return self.process_registry.process(
            function,
            id=id,
            version=version,
            title=title,
            description=description,
            input_fields=input_fields,
            output_fields=output_fields,
        )

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
