#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import datetime
import inspect
import traceback
import uuid
import warnings
from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Optional

import pydantic

from s2gos_common.models import (
    JobInfo,
    JobResults,
    JobStatus,
    JobType,
    ProcessRequest,
    Schema,
    Subscriber,
)

from .process import Process
from .reporter import CallbackReporter


class JobCancelledException(Exception):
    """Raised if a job's cancellation has been requested."""


class JobContext(ABC):
    """
    Report process progress and check for task cancellation.

    A process function can retrieve the current job context

    1. via [JobContext.get()][s2gos_common.process.JobContext.get] from
       within a process function, or
    2. as a function argument of type [JobContext][s2gos_common.process.JobContext].
    """

    @classmethod
    def get(cls) -> "JobContext":
        """
        Get the current job context.

        Returns the current job context that can be used by
        process functions to report job progress in percent
        or via messages and to check whether cancellation
        has been requested.
        This function is intended to be called from within
        a process function executed as a job. If called as a usual
        Python function (without a job serving as context), the
        returned context will have no-op methods only.

        Returns:
            An instance of the current job context.
        """
        frame = inspect.currentframe()
        try:
            while frame:
                job_context = frame.f_locals.get("__job_context__")
                if isinstance(job_context, JobContext):
                    return job_context
                frame = frame.f_back
        finally:
            # Always free alive frame-references
            del frame
        # noinspection PyUnreachableCode
        warnings.warn(
            "cannot determine current job context; using non-functional dummy"
        )
        return NullJobContext()

    @abstractmethod
    def report_progress(
        self,
        progress: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Report task progress.

        Args:
            progress: Progress in percent.
            message: Detail progress message.

        Raises:
            JobCancellationException: if an attempt has been made
                to cancel this job.
        """

    @abstractmethod
    def is_cancelled(self) -> bool:
        """Test whether an attempt has been made to cancel this job.
        It may still be running though.

        Returns:
            `True` if so, `False` otherwise.
        """

    @abstractmethod
    def check_cancelled(self) -> None:
        """Raise a `JobCancellationException`, if
        an attempt has been made to cancel this job.
        """


class Job(JobContext):
    """
    Represents an execution of a user function.

    Args:
        process: The process that created this job.
        job_id: A job identifier.
        function_kwargs: The user function's keyword arguments.
            A keyword must be a valid Python identifier or a
            sequence of Python identifiers separated by the dot
            (`.`) character.
        subscriber: Optional subscriber URIs.
    """

    @classmethod
    def create(
        cls,
        process: Process,
        request: ProcessRequest,
        job_id: Optional[str] = None,
    ) -> "Job":
        """
        Create a new job for the given process and process request.

        Args:
            process: The process.
            request: The process request.
                Names of request inputs must be valid Python identifiers or
                sequences of Python identifiers separated by the dot
                (`.`) character. The latter is used to set nested input objects.
            job_id: Optional job identifier.
                If omitted, a unique identifier will be generated (UUID4).

        Returns:
            A new job instance.

        Raises:
            pydantic.ValidationError: if an input value is not valid
                with respect to its process input description.
        """
        process_desc = process.description
        input_params = request.inputs or {}
        input_default_params = {
            input_name: input_info.schema_.default
            for input_name, input_info in (process_desc.inputs or {}).items()
            if isinstance(input_info.schema_, Schema)
            and input_info.schema_.default is not None
        }
        input_values: dict[str, Any] = {}
        for input_name in (process_desc.inputs or {}).keys():
            if input_name in input_params:
                input_values[input_name] = input_params[input_name]
            elif input_name in input_default_params:
                input_values[input_name] = input_default_params[input_name]

        model_instance: pydantic.BaseModel = process.model_class(**input_values)

        function_kwargs = {
            k: getattr(model_instance, k)
            for k in process.model_class.model_fields.keys()
            if k in input_values
        }

        return Job(
            process=process,
            job_id=job_id or f"{uuid.uuid4()}",
            function_kwargs=function_kwargs,
            subscriber=request.subscriber,
        )

    def __init__(
        self,
        *,
        process: Process,
        job_id: str,
        function_kwargs: dict[str, Any],
        subscriber: Optional[Subscriber] = None,
    ):
        """Internal constructor.
        Use `Job.create() instead.`
        """
        self.process = process
        # noinspection PyTypeChecker
        self.job_info = JobInfo(  # noqa [call-arg]
            type=JobType.process,
            processID=process.description.id,
            jobID=job_id,
            status=JobStatus.accepted,
            created=self._now(),
        )
        self.function_kwargs = function_kwargs
        self.cancelled = False
        self.future: Optional[Future] = None
        self.subscriber = subscriber
        self._reporter: CallbackReporter | None = None

    @property
    def reporter(self) -> CallbackReporter:
        if self._reporter is None:
            self._reporter = CallbackReporter()
        return self._reporter

    def report_progress(
        self, progress: Optional[int] = None, message: Optional[str] = None
    ):
        self.check_cancelled()
        # noinspection PyTypeChecker
        self.job_info.updated = self._now()
        if progress is not None:
            self.job_info.progress = progress
        if message is not None:
            self.job_info.message = message
        self._maybe_notify_in_progress()

    def is_cancelled(self) -> bool:
        return self.cancelled

    def check_cancelled(self):
        if self.cancelled:
            raise JobCancelledException

    def cancel(self):
        """Request job cancellation.
        Note, actual cancellation will happen
        only from within the user function.
        """
        self.cancelled = True

    def run(self) -> JobResults | None:
        """Run this job."""

        # Make the job (context) findable by get_job_context()
        # through the local variable __job_context__
        ctx = __job_context__ = self  # noqa: F841

        function_kwargs: dict[str, Any] = dict(self.function_kwargs)

        # use "inputs arg", if needed
        inputs_arg = self.process.inputs_arg
        if inputs_arg:
            function_kwargs.pop(inputs_arg, None)
            function_kwargs = {inputs_arg: self.process.model_class(**function_kwargs)}

        # inject job context, if needed
        ctx_arg = self.process.job_ctx_arg
        if ctx_arg:
            function_kwargs.pop(ctx_arg, None)
            function_kwargs = {ctx_arg: ctx, **function_kwargs}

        self._start_job()
        try:
            self.check_cancelled()
            function_result = self.process.function(**function_kwargs)
            self._finish_job(JobStatus.successful)
            job_results = self._get_job_results(function_result)
            self._maybe_notify_success(job_results)
            return job_results
        except JobCancelledException:
            self._finish_job(JobStatus.dismissed)
            self._maybe_notify_failed()
        except Exception as e:
            self._finish_job(JobStatus.failed, exception=e)
            self._maybe_notify_failed()
        return None

    def _get_job_results(self, function_result: Any) -> JobResults:
        assert self.job_info.status == JobStatus.successful
        assert self.job_info.processID is not None
        outputs = self.process.description.outputs or {}
        output_count = len(outputs)
        return JobResults(
            **{
                output_name: (
                    function_result if output_count == 1 else function_result[i]
                )
                for i, output_name in enumerate(outputs.keys())
            }
        )

    def _start_job(self):
        # noinspection PyTypeChecker
        self.job_info.started = self._now()
        self.job_info.status = JobStatus.running

    def _finish_job(self, job_status: JobStatus, exception: Optional[Exception] = None):
        # noinspection PyTypeChecker
        self.job_info.finished = self._now()
        self.job_info.status = job_status
        if exception is not None:
            self.job_info.message = f"{exception}"
            self.job_info.traceback = traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )

    def _maybe_notify_success(self, job_results: JobResults):
        if self.subscriber is not None and self.subscriber.successUri is not None:
            url = str(self.subscriber.successUri)
            data = job_results.model_dump(mode="json", by_alias=True)
            self.reporter.report(url, data)

    def _maybe_notify_failed(self):
        if self.subscriber is not None:
            self._maybe_notify_current_job_info(self.subscriber.failedUri)

    def _maybe_notify_in_progress(self):
        if self.subscriber is not None:
            self._maybe_notify_current_job_info(self.subscriber.inProgressUri)

    def _maybe_notify_current_job_info(self, url: pydantic.AnyUrl | None):
        if url is not None:
            data = self.job_info.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
                exclude_unset=True,
            )
            self.reporter.report(str(url), data)

    @staticmethod
    def _now() -> datetime.datetime:
        # noinspection PyTypeChecker
        return datetime.datetime.now(tz=datetime.timezone.utc)


class NullJobContext(JobContext):
    """A job context used if a real one could not be provided."""

    def report_progress(
        self, progress: Optional[int] = None, message: Optional[str] = None
    ) -> None:
        """Does nothing."""

    def is_cancelled(self) -> bool:
        """Returns `False`."""
        return False

    def check_cancelled(self) -> None:
        """Does nothing."""
