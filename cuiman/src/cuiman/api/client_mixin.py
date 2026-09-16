#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import time
import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Literal, Optional

from gavicore.dru_models import OgcApplicationPackage
from gavicore.models import (
    ApiError,
    JobInfo,
    JobResults,
    JobStatus,
    ProcessDescription,
    ProcessSummary,
)
from gavicore.util.request import ExecutionRequest
from gavicore.util.runsync import run_sync

from .auth.session import resolve_auth_headers
from .config import ClientConfig
from .defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from .exceptions import ClientError, ClientWarning
from .opener import JobResultOpenContext, JobResultStatusError
from .opener.opener import open_job_result
from .transport import Transport, TransportArgs
from .transport.httpx import HttpxTransport

if TYPE_CHECKING:
    pass

# -----------------------------------------------------
# IMPORTANT: Sync changes here with AsyncClientMixin!
# -----------------------------------------------------


# noinspection PyShadowingBuiltins
class ClientMixin(ABC):
    """
    Extra methods for the API client (synchronous mode).
    """

    _transport: Transport | None
    _debug: bool

    def login(
        self, *, interactive: bool = True, no_browser: bool = False, force: bool = False
    ) -> None:
        """Prepare authentication, reusing existing credentials when possible.

        Explicit login may prompt for credentials or open an OIDC browser.
        API methods call this with ``interactive=False`` and raise a
        ``LoginRequiredError`` when user interaction is needed.
        Use ``force=True`` to bypass existing tokens and authenticate afresh.
        A successful login also updates an existing HTTPX transport.
        """
        headers = resolve_auth_headers(
            self.config.auth,
            interactive=interactive,
            no_browser=no_browser,
            force=force,
        )
        if self._transport is not None and isinstance(self._transport, HttpxTransport):
            self._transport.headers = headers

    def _get_transport(self) -> Transport:
        if self._transport is None:
            self.login(interactive=False)
            assert self.config.api_url is not None
            self._transport = HttpxTransport(
                api_url=f"{self.config.api_url.rstrip('/')}/",
                headers=self.config.auth_headers,
                return_type_map=self.config.return_type_map,
                token_refresher=self.config._maybe_make_token_refresher(),
                debug=self._debug,
            )
        return self._transport

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
        output_name: str | None = None,
        data_type: type | None = None,
        media_type: str | None = None,
        poll_interval: float = DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
        timeout: float = DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
        **options: Any,
    ) -> Any:
        """Open the results of the job given by its ID.

        Args:
            job_id: the job ID
            output_name: the name of the output to be opened.
            data_type: the expected/desired data type to be returned.
                If provided, the return value will be of that type.
                If not provided, the return value will be the type
                decided by the opener.
            media_type: the media type of the output produced.
                Only needed, if the output does not provide its
                media type or if its media type should be overridden.
            poll_interval: interval in seconds between job status polls.
                Applies while job status is still "accepted" or "running".
            timeout: maximum time in seconds to wait for job completion.
            options: additional opener-specific options.

        Returns:
            The job result value.

        Raises:
            ClientError: if an API error occurs
            JobResultOpenError: if an opener error occurs
            JobResultStatusError: if the job failed or was canceled
            TimeoutError: if the job does not finish within the timeout
        """
        deadline = time.time() + timeout
        while True:
            job_info = self.get_job(job_id)
            if job_info.status not in (JobStatus.accepted, JobStatus.running):
                break
            if time.time() >= deadline:
                raise TimeoutError(
                    f"Cannot open result of job #{job_id}; "
                    f"it did not finish within {timeout} seconds"
                )
            time.sleep(poll_interval)
        if job_info.status != JobStatus.successful:
            raise JobResultStatusError(job_info)
        job_results = self.get_job_results(job_id)
        process_id = job_info.processID
        process_description: ProcessDescription | None = None
        if process_id:
            try:
                process_description = self.get_process(process_id)
            except ClientError:
                warnings.warn(
                    "An error occurred while getting process "
                    f"description for process ID {process_id!r}",
                    category=ClientWarning,
                    stacklevel=2,
                )
        ctx = JobResultOpenContext(
            config=self.config,
            job_id=job_id,
            job_results=job_results,
            process_description=process_description,
            output_name=output_name,
            data_type=data_type,
            _media_type=media_type,
            options=options,
        )
        opener_registry = self.config.get_job_result_opener_registry()
        return run_sync(
            open_job_result,
            ctx,
            *opener_registry.opener_types,
        )

    def deploy_process(
        self,
        content: bytes,
        encoding: Literal[
            "application/cwl", "application/cwl+json", "application/cwl+yaml"
        ],
        w: str | None = None,
        **kwargs: Any,
    ) -> Optional[ProcessSummary]:
        """Deploy a new process to a server supporting
        OGC API - Processes — Part 2 (DRU) by providing a process
        description in a supported format.

        Depending on the service implementation,
        the server may not return a response body.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#deploy).

        Args:
          content: EOAP to deploy as a raw bytes object.
          encoding: Format of the EOAP to deploy.
          w: Optionally point to the workflow identifier for deploying a
             CWL containing multiple workflow definitions.

        Returns:
          ProcessSummary: Process summary of newly added process, when the server
            returns such an object.

        Raises:
          ClientError: If the call to the web service fails
            with a status code != `2xx`.

            - `403`: Process exists and isn't mutable.
            - `405`: The server does not allow this method,
              i.e. DRU is not implemented
            - `409`: Process exists and is mutable.
            - `415`: Unsupported media type for supplied process.
            - `500`: A server error occurred.
        """
        transport = self._get_transport()
        kwargs["content"] = content

        try:
            transport.headers["Content-Type"] = encoding  # type: ignore[attr-defined]
            return transport.call(
                TransportArgs(
                    path="/processes",
                    method="post",
                    path_params={"w": w},
                    return_types={"201": ProcessSummary, "202": None},
                    error_types={
                        "403": ApiError,
                        "405": ApiError,
                        "409": ApiError,
                        "415": ApiError,
                        "501": ApiError,
                    },
                    extra_kwargs=kwargs,
                )
            )
        finally:
            del transport.headers["Content-Type"]  # type: ignore[attr-defined]

    def replace_process(
        self,
        process_id: str,
        content: bytes,
        encoding: Literal[
            "application/cwl", "application/cwl+json", "application/cwl+yaml"
        ],
        w: str | None = None,
        **kwargs: Any,
    ) -> Optional[ProcessSummary]:
        """Replace an exisitng and mutable process by providing a new
        process description in a supported format.

        Depending on the service implementation,
        the server may not return a response body.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#replace).

        Args:
          process_id: Unique identifier of registered process
            that is to be replaced.
          content: EOAP to deploy as a raw bytes object.
          encoding: Format of the EOAP to deploy.
          w: Optionally point to the workflow identifier for deploying a
             CWL containing multiple workflow definitions.

        Returns:
          ProcessSummary: Process summary of newly added process, when the server
            returns such an object.

        Raises:
          ClientError: If the call to the web service fails
            with a status code != `2xx`.

            - `403`: Process exists and isn't mutable.
            - `405`: The server does not allow this method,
              i.e. DRU is not implemented
            - `409`: Process exists and is mutable.
            - `415`: Unsupported media type for supplied process.
            - `500`: A server error occurred.
        """
        transport = self._get_transport()
        kwargs["content"] = content

        try:
            transport.headers["Content-Type"] = encoding  # type: ignore[attr-defined]
            return transport.call(
                TransportArgs(
                    path="/processes/{processId}",
                    method="put",
                    path_params={"processId": process_id, "w": w},
                    return_types={
                        "200": ProcessSummary,
                        "201": ProcessSummary,
                        "202": ProcessSummary,
                        "204": None,
                    },
                    error_types={
                        "403": ApiError,
                        "405": ApiError,
                        "409": ApiError,
                        "415": ApiError,
                        "501": ApiError,
                    },
                    extra_kwargs=kwargs,
                )
            )
        finally:
            del transport.headers["Content-Type"]  # type: ignore[attr-defined]

    def undeploy_process(self, process_id: str, **kwargs: Any) -> None:
        """Remove an exisitng and mutable process by providing
        its process id.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#undeploy).

        Args:
            process_id: Unique identifier of registered process
                that is to be replaced.

        Raises:
          ClientError: If the call to the web service fails
            with a status code != `2xx`.

            - `403`: The requested process is not mutable
            - `404`: The requested URI was not found.
            - `405`: The server does not allow this method,
              i.e. DRU is not implemented
            - `500`: A server error occurred.
        """
        transport = self._get_transport()
        return transport.call(
            TransportArgs(
                path="/processes/{processId}",
                method="delete",
                path_params={"processId": process_id},
                return_types={"204": None},
                error_types={
                    "403": ApiError,
                    "404": ApiError,
                    "405": ApiError,
                    "501": ApiError,
                },
                extra_kwargs=kwargs,
            )
        )

    def get_formal_description(
        self, process_id: str, **kwargs: Any
    ) -> OgcApplicationPackage:
        """Retrieve a formal description of a previously deployed process
        via the deploy operation.
        The returned description relates to the most recent deployment.

        For more information, see
        [OGC API - Processes — Part 2 (DRU)](https://docs.ogc.org/DRAFTS/20-044.html#application-package-retrieval-operation).

        Args:
            process_id: Unique identifier of registered process.

        Raises:
          ClientError: If the call to the web service fails
            with a status code != `2xx`.

            - `403`: The requested process is not mutable
            - `404`: The requested process was not found.
            - `405`: The server does not allow this method,
              i.e. DRU is not implemented
            - `500`: A server error occurred.
        """
        transport = self._get_transport()
        try:
            transport.headers["Accept"] = "application/ogcapppkg+json"  # type: ignore[attr-defined]
            return transport.call(
                TransportArgs(
                    path="/processes/{processId}/package",
                    method="get",
                    path_params={"processId": process_id},
                    return_types={"200": OgcApplicationPackage},
                    error_types={
                        "403": ApiError,
                        "404": ApiError,
                        "405": ApiError,
                        "501": ApiError,
                    },
                    extra_kwargs=kwargs,
                )
            )
        finally:
            del transport.headers["Accept"]  # type: ignore[attr-defined]
