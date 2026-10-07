#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import threading
import time
import warnings
from abc import abstractmethod
from typing import Any, overload

import httpx2
from authlib.integrations.base_client.errors import InvalidTokenError
from authlib.integrations.httpx_client import OAuth2Client

from gavicore.models import JobInfo, JobResults, JobStatus, ProcessDescription
from gavicore.util.request import ExecutionRequest
from gavicore.util.runsync import run_sync

from .auth.config import OidcAuthConfig
from .auth.interactive import authorize
from .auth.oidc import LoopbackCallbackServer
from .client_mixin_base import ClientMixinBase
from .context import (
    _UNSET,
    JobResultContext,
    _Unset,
    _validate_open_arguments,
    describe_job_output,
)
from .defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from .exceptions import ClientError, ClientWarning
from .listing import _validate_listing_arguments, list_job_result_resources
from .metadata import DiscoveryLimits
from .opener import JobResultStatusError
from .opener.opener import open_job_result
from .resources import JobResultResource, JobResultResourceListing
from .transport import Transport

# -----------------------------------------------------
# IMPORTANT: Sync changes here with AsyncClientMixin!
# -----------------------------------------------------


# noinspection PyShadowingBuiltins
class ClientMixin(ClientMixinBase[httpx2.Client]):
    """
    Extra methods for the API client (synchronous mode).
    """

    _transport: Transport | None

    def _init_client_runtime(self) -> None:
        super()._init_client_runtime()
        self._runtime_lock = threading.RLock()
        self._job_result_lock = threading.RLock()

    def close(self) -> None:
        """Close owned connections. A closed client cannot be used again."""
        with self._runtime_lock:
            self._closed = True
            self._job_result_metadata_cache = None
            transport, self._transport = self._transport, None
            try:
                if transport is not None:
                    transport.close()
            finally:
                if self._http_client is not None:
                    self._http_client.close()
                self._http_client = None

    def login(
        self,
        *,
        interactive: bool = True,
        no_browser: bool = False,
        force: bool = False,
        save: bool = False,
    ) -> None:
        """Prepare authentication using the client's persistent HTTP session.

        Use force to acquire a fresh token. Requests never prompt or open a
        browser. With save=True, failure to save credentials raises an error.
        """
        with self._runtime_lock:
            self._login(
                interactive=interactive, no_browser=no_browser, force=force, save=save
            )

    def _login(
        self,
        *,
        interactive: bool = False,
        no_browser: bool = False,
        force: bool = False,
        save: bool = False,
    ) -> None:
        self._require_open()
        auth = self._credentials(interactive=interactive, force=force)
        self._configure_http_client(auth, self._updated_token)
        self._discover()
        client = self._http_client
        response = None
        if isinstance(client, OAuth2Client) and client.token and not force:
            if not client.ensure_active_token(client.token):
                raise InvalidTokenError()
        elif isinstance(auth, OidcAuthConfig):
            assert isinstance(client, OAuth2Client)
            with LoopbackCallbackServer() as server:
                url, state, verifier = self._authorization(client, server)
                code = authorize(server, url, state, no_browser=no_browser)
                response = client.fetch_token(code=code, code_verifier=verifier)
                self._validate_oidc_token(required=True)
        elif request := self._login_request(force=force):
            response = request()
        self._accept_login(response, force=force, save=save)

    def _discover(self) -> None:
        if url := self._discovery_url:
            assert self._http_client is not None
            self._accept_discovery(self._http_client.request("GET", url, auth=None))

    def _validate_oidc_token(self, *, required: bool = False) -> None:
        with self._oidc_validation(required=required) as url:
            if url:
                assert self._http_client is not None
                response = self._http_client.request("GET", url, auth=None)
                self._validate_id_token(response, required=required)

    def _updated_token(self, _token: dict[str, Any], **_previous: Any) -> None:
        self._validate_oidc_token()
        self._save_credentials()

    def logout(self) -> None:
        """Revoke an OIDC token when supported, remove local secrets, and close."""
        with self._runtime_lock:
            self._require_open()
            try:
                if self._can_revoke:
                    self._configure_http_client(self.config.auth, self._updated_token)
                    self._discover()
                    if options := self._revocation():
                        assert isinstance(self._http_client, OAuth2Client)
                        response = self._http_client.revoke_token(**options)
                        response.raise_for_status()
            finally:
                self._closed = True
                try:
                    self._forget_credentials()
                finally:
                    self.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        with self._runtime_lock:
            self._login()
            assert self._http_client is not None
            return self._http_client.request(
                method, url, **self._request_options(kwargs)
            )

    def _app_callbacks(self) -> dict[str, Any]:
        self._require_open()

        async def prepare() -> None:
            await asyncio.to_thread(self.login, interactive=False)

        async def request(method: str, url: str, **kwargs: Any) -> httpx2.Response:
            return await asyncio.to_thread(self._request, method, url, **kwargs)

        return dict(prepare=prepare, request=request)

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

    def list_job_result_resources(
        self,
        job_id: str,
        *,
        output_name: str | None = None,
        parent_id: str | None = None,
        kind: str | None = None,
        data_type: type | None = None,
        limits: DiscoveryLimits | None = None,
        refresh: bool = False,
    ) -> JobResultResourceListing:
        """Discover selectable targets and reader availability for a completed job.

        The default view shows STAC Assets, ordinary outputs, declared descendants,
        and deferred Catalog/Collection containers. Select ``kind`` for another
        view or ``parent_id`` for immediate loaded members; neither selection nor
        rendering reads Asset data. Explicit remote traversal and continuation
        are not yet implemented. This synchronous method runs the same discovery
        and assessment pipeline as ``AsyncClient``.

        Args:
            job_id: Producing job identifier, never a resource URL.
            output_name: Original output to resolve; omit to include every output.
            parent_id: Exact loaded resource selector for an immediate-member view.
            kind: Semantic kind to filter, such as ``stac-item`` or ``asset``.
            data_type: Desired Python return type for opener candidate assessment.
            limits: Request, response, time, and expansion bounds.
            refresh: Discard cached metadata and failures before this listing.

        Returns:
            A portable snapshot with loaded rows, output states, and diagnostics.
            Each row includes opener availability; previews remain unassessed.

        Raises:
            JobResultStatusError: The job is unfinished, failed, or dismissed;
                listing checks once and does not wait for completion.
            ResourceNotFoundError: The output or loaded parent selector is absent.
            ClientError: Processing API retrieval failed.
            TypeError: Listing arguments are invalid.
        """
        _validate_listing_arguments(
            job_id, output_name, parent_id, kind, data_type, limits, refresh
        )
        self._require_open()
        with self._job_result_lock:
            job = self.get_job(job_id)
            if job.status != JobStatus.successful:
                raise JobResultStatusError(job)
            results = self.get_job_results(job_id)
            process = None
            if job.processID:
                try:
                    process = self.get_process(job.processID)
                except ClientError:
                    warnings.warn(
                        "Process description unavailable during resource discovery",
                        ClientWarning,
                        stacklevel=2,
                    )
            context = self._job_result_context(
                job_id, limits=limits, data_type=data_type, refresh=refresh
            )
            return run_sync(
                list_job_result_resources,
                context,
                results,
                process,
                output_name=output_name,
                parent_id=parent_id,
                kind=kind,
            )

    @overload
    def open_job_result(
        self,
        job_id: str,
        output_name: str | None = None,
        data_type: type | None = None,
        media_type: str | None = None,
        poll_interval: float = DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
        timeout: float = DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
        **options: Any,
    ) -> Any: ...

    @overload
    def open_job_result(
        self,
        job_id: JobResultResource,
        *,
        data_type: type | None = None,
        media_type: str | None = None,
        **options: Any,
    ) -> Any: ...

    def open_job_result(
        self,
        job_id: str | JobResultResource,
        output_name: str | None | _Unset = _UNSET,
        data_type: type | None = None,
        media_type: str | None = None,
        poll_interval: float | _Unset = _UNSET,
        timeout: float | _Unset = _UNSET,
        **options: Any,
    ) -> Any:
        """Open one original job output or an explicitly selected resource.

        Resource calls open that resource directly using this client's settings.
        Explicit output_name, poll_interval, or timeout arguments with a resource
        raise TypeError, including explicitly supplied None/default values.
        Strings always identify jobs. Multiple outputs require output_name.

        Args:
            job_id: the job ID or selected JobResultResource
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
            TypeError: if the target or resource arguments are invalid
        """
        output_name, poll_interval, timeout = _validate_open_arguments(
            job_id,
            output_name,
            poll_interval,
            timeout,
            default_poll=DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
            default_timeout=DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
        )
        self._require_open()
        context = JobResultContext(
            config=self.config,
            data_type=data_type,
            media_type=media_type,
            options=options,
        )
        if isinstance(job_id, JobResultResource):
            return run_sync(
                open_job_result,
                job_id,
                *self.config.get_job_result_opener_registry().opener_types,
                context=context,
            )
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
        resource = run_sync(
            describe_job_output,
            job_id,
            job_results,
            output_name,
            service_url=self.config.api_url,
            process_description=process_description,
            context=context,
        )
        opener_registry = self.config.get_job_result_opener_registry()
        return run_sync(
            open_job_result,
            resource,
            *opener_registry.opener_types,
            context=context,
        )
