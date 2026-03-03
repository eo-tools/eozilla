#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any

from anyio.to_process import run_sync

from cuiman.api.config import ClientConfig
from cuiman.api.opener import OpenerContext
from gavicore.models import ProcessDescription, JobResults, JobInfo, JobStatus
from gavicore.util.request import ExecutionRequest


# noinspection PyShadowingBuiltins
class ClientMixin(ABC):
    """
    Extra methods for the API client (synchronous mode).
    """

    @property
    @abstractmethod
    def config(self) -> ClientConfig:
        """Will be overridden by the actual client class."""

    @abstractmethod
    def get_process(self, process_id: str, **kwargs: Any) -> ProcessDescription:
        """Will be overridden by the actual client class."""

    @abstractmethod
    def get_job(self, job_id: str, **kwargs: Any) -> JobInfo:
        """Will be overridden by the actual client class."""

    @abstractmethod
    def get_job_results(self, job_id: str, **kwargs: Any) -> JobResults:
        """Will be overridden by the actual client class."""

    def create_execution_request(
        self,
        process_id: str,
        dotpath: bool = False,
    ) -> ExecutionRequest:
        """
        Create a template for an execution request
        generated from the process description of the
        given process identifier.

        Args:
            process_id: The process identifier
            dotpath: Whether to create dot-separated input
                names for nested object values

        Returns:
            The execution request template.

        Raises:
            ClientError: if an API error occurs
        """
        process_description = self.get_process(process_id)
        return ExecutionRequest.from_process_description(
            process_description, dotpath=dotpath
        )

    def open_job_result(
        self,
        job_id: str,
        data_type: type | None = None,
        output_name: str | None = None,
        **options: Any,
    ) -> Any:
        """Open the results of the job given by its ID.

        Args:
            job_id: the job ID
            data_type: the expected data type to be returned.
                If provided, the return value will be of that type.
            output_name: the name of the output to be opened.
            options: additional opener-specific options.

        Returns:
            The job result value.

        Raises:
            ClientError: if an API error occurs
            OpenerError: if an opener error occurs
        """
        job_info = self.get_job(job_id)
        if job_info.status != JobStatus.successful:
            raise ValueError(
                f"Cannot open result of job #{job_id} with status {job_info.status}."
            )
        job_results = self.get_job_results(job_id)
        process_description = self.get_process(job_info.processID)
        ctx = OpenerContext(
            config=self.config,
            job_id=job_id,
            job_results=job_results,
            process_description=process_description,
            data_type=data_type,
            output_name=output_name,
            options=options,
        )
        return run_sync(self.config.opener_registry.open_result(ctx))
