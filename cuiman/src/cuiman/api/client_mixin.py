#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Any, Optional

from gavicore.models import JobInfo, JobResults, ProcessDescription
from gavicore.util.request import ExecutionRequest

from .openers import JobResultOpenerRegistry, build_open_job_result_context


# noinspection PyShadowingBuiltins
class ClientMixin(ABC):
    """Extra methods for the synchronous API client."""

    @property
    @abstractmethod
    def config(self) -> Any:
        """Return the client configuration instance."""

    @abstractmethod
    def get_process(self, process_id: str, **kwargs: Any) -> ProcessDescription:
        """Get process description for `process_id`."""

    @abstractmethod
    def get_job(self, job_id: str, **kwargs: Any) -> JobInfo:
        """Get job information for `job_id`."""

    @abstractmethod
    def get_job_results(self, job_id: str, **kwargs: Any) -> JobResults:
        """Get job results for `job_id`."""

    def create_execution_request(
        self,
        process_id: str,
        dotpath: bool = False,
    ) -> ExecutionRequest:
        """Create an execution request template from a process description.

        Args:
            process_id: The process identifier.
            dotpath: Whether to create dot-separated input names for nested values.

        Returns:
            The execution request template.
        """
        process_description = self.get_process(process_id)
        return ExecutionRequest.from_process_description(
            process_description, dotpath=dotpath
        )

    @property
    def result_openers(self) -> JobResultOpenerRegistry:
        """Return the opener registry configured by the active config class."""
        return type(self.config).get_result_openers()

    def set_result_openers(self, result_openers: JobResultOpenerRegistry) -> None:
        """Set the opener registry on the active config class.

        This configures application-wide opener behavior for all clients using the
        same `ClientConfig` subclass.
        """
        type(self.config).result_openers = result_openers

    def register_result_opener(self, data_type: str, opener: Any) -> None:
        """Register an opener function for a `data_type` key."""
        self.result_openers.register_data_type(data_type, opener)

    def open_job_result(
        self,
        job_id_or_results: str | JobResults,
        data_type: Optional[str] = None,
        **options: Any,
    ) -> Any:
        """Open or read a job result using registered opener functions.

        This method resolves job results and dispatches to an opener from the
        configured :class:`~cuiman.api.openers.JobResultOpenerRegistry`.

        ## How to extend opener capabilities

        Applications can add support for domain-specific result types (e.g. S3,
        GCS, Zarr, NetCDF, GeoTIFF, xarray objects) by registering custom openers:

        1. Implement an opener callable ``opener(context) -> Any`` that accepts an
           :class:`~cuiman.api.openers.OpenJobResultContext`.
           Use ``context.output_value`` for the normalized selected output value,
           ``context.output_name`` for the selected output id, and
           ``context.options`` for user-provided hints.
        2. Register by data type key using
           :meth:`register_result_opener` (or directly on
           ``client.result_openers.register_data_type(...)``).
        3. Call ``open_job_result(..., data_type="your-type")`` to force that
           opener, or omit ``data_type`` and let inference
           (:func:`~cuiman.api.openers.infer_data_type`) choose based on metadata.

        For application-wide behavior, configure the registry on a custom
        ``ClientConfig`` subclass via ``result_openers`` /
        ``get_result_openers()`` and use that subclass as the default config.

        Args:
            job_id_or_results: Either a job identifier or a pre-fetched `JobResults`.
            data_type: Optional explicit data type key for opener dispatch.
            **options: Optional opener hints such as ``output_name``, ``process_id``,
                ``process_description``, ``media_type``, request ``headers``, and
                ``timeout``. Custom openers may consume additional option keys.

        Returns:
            Any value produced by the selected job-result opener.
        """
        if isinstance(job_id_or_results, JobResults):
            job_results = job_id_or_results
        else:
            job_results = self.get_job_results(job_id_or_results)

        process_description = options.pop("process_description", None)
        if process_description is None:
            process_id = options.get("process_id")
            if process_id is None and isinstance(job_id_or_results, str):
                process_id = self.get_job(job_id_or_results).processID
            if process_id:
                process_description = self.get_process(process_id)

        context = build_open_job_result_context(
            client=self,
            job_results=job_results,
            data_type=data_type,
            process_description=process_description,
            options=options,
        )
        return self.result_openers.open(context)
