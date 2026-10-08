#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import threading
import warnings
from abc import abstractmethod
from typing import Any, overload

import httpx2
from authlib.integrations.httpx_client import AsyncOAuth2Client

from gavicore.models import JobInfo, JobResults, JobStatus, ProcessDescription
from gavicore.util.request import ExecutionRequest

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
from .transport import AsyncTransport

# -----------------------------------------------------
# IMPORTANT: Sync changes here with ClientMixin!
# -----------------------------------------------------


# noinspection PyShadowingBuiltins
class AsyncClientMixin(ClientMixinBase[httpx2.AsyncClient]):
    """
    Extra methods for the API client (asynchronous mode).
    """

    _async_mode = True
    _transport: AsyncTransport | None

    def _init_client_runtime(self) -> None:
        super()._init_client_runtime()
        self._runtime_lock = asyncio.Lock()
        self._job_result_lock = asyncio.Lock()
        self._owner_loop: asyncio.AbstractEventLoop | None = None

    def _bind_loop(self) -> asyncio.AbstractEventLoop:
        loop = asyncio.get_running_loop()
        if self._owner_loop is not None and self._owner_loop is not loop:
            raise RuntimeError("AsyncClient must be used on its owning event loop.")
        self._owner_loop = loop
        return loop

    async def close(self) -> None:
        """Close owned connections. A closed client cannot be used again."""
        self._bind_loop()
        async with self._runtime_lock:
            await self._close()

    async def _close(self) -> None:
        """Close connections while the caller holds the owner lock."""
        self._closed = True
        self._job_result_metadata_cache = None
        transport, self._transport = self._transport, None
        try:
            if transport is not None:
                await transport.async_close()
        finally:
            if self._http_client is not None:
                await self._http_client.aclose()
            self._http_client = None

    async def login(
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
        self._bind_loop()
        async with self._runtime_lock:
            await self._login(
                interactive=interactive, no_browser=no_browser, force=force, save=save
            )

    async def _login(
        self,
        *,
        interactive: bool = False,
        no_browser: bool = False,
        force: bool = False,
        save: bool = False,
    ) -> None:
        self._require_open()
        auth = (
            await asyncio.to_thread(self._credentials, interactive=True, force=force)
            if interactive
            else self._credentials(interactive=False, force=force)
        )
        self._configure_http_client(auth, self._updated_token)
        await self._discover()
        client = self._http_client
        response = None
        if isinstance(client, AsyncOAuth2Client) and client.token and not force:
            await client.ensure_active_token(client.token)
        elif isinstance(auth, OidcAuthConfig):
            assert isinstance(client, AsyncOAuth2Client)
            with LoopbackCallbackServer() as server:
                url, state, verifier = self._authorization(client, server)
                cancelled = threading.Event()
                try:
                    code = await asyncio.to_thread(
                        authorize,
                        server,
                        url,
                        state,
                        no_browser=no_browser,
                        cancelled=cancelled,
                    )
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
                response = await client.fetch_token(code=code, code_verifier=verifier)
                await self._validate_oidc_token(required=True)
        elif request := self._login_request(force=force):
            response = await request()
        self._accept_login(response, force=force, save=save)

    async def _discover(self) -> None:
        if url := self._discovery_url:
            assert self._http_client is not None
            self._accept_discovery(
                await self._http_client.request("GET", url, auth=None)
            )

    async def _validate_oidc_token(self, *, required: bool = False) -> None:
        with self._oidc_validation(required=required) as url:
            if url:
                assert self._http_client is not None
                response = await self._http_client.request("GET", url, auth=None)
                self._validate_id_token(response, required=required)

    async def _updated_token(self, _token: dict[str, Any], **_previous: Any) -> None:
        await self._validate_oidc_token()
        self._save_credentials()

    async def logout(self) -> None:
        """Revoke an OIDC token when supported, remove local secrets, and close."""
        self._bind_loop()
        async with self._runtime_lock:
            self._require_open()
            try:
                if self._can_revoke:
                    self._configure_http_client(self.config.auth, self._updated_token)
                    await self._discover()
                    if options := self._revocation():
                        assert isinstance(self._http_client, AsyncOAuth2Client)
                        response = await self._http_client.revoke_token(**options)
                        response.raise_for_status()
            finally:
                self._closed = True
                try:
                    self._forget_credentials()
                finally:
                    await self._close()

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx2.Response:
        self._bind_loop()
        async with self._runtime_lock:
            await self._login()
            assert self._http_client is not None
            return await self._http_client.request(
                method, url, **self._request_options(kwargs)
            )

    def _app_callbacks(self) -> dict[str, Any]:
        self._require_open()
        loop = self._bind_loop()

        def require_running_owner() -> None:
            self._require_open()
            if not loop.is_running():
                raise RuntimeError("The AsyncClient owning event loop is not running.")

        async def prepare() -> None:
            require_running_owner()
            await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(self.login(interactive=False), loop)
            )

        async def request(method: str, url: str, **kwargs: Any) -> httpx2.Response:
            require_running_owner()
            return await asyncio.wrap_future(
                asyncio.run_coroutine_threadsafe(
                    self._request(method, url, **kwargs), loop
                )
            )

        return dict(prepare=prepare, request=request)

    @abstractmethod
    async def get_process(self, process_id: str, **kwargs: Any) -> ProcessDescription:
        """Will be overridden by the actual client class."""

    @abstractmethod
    async def get_job(self, job_id: str, **kwargs: Any) -> JobInfo:
        """Will be overridden by the actual client class."""

    @abstractmethod
    async def get_job_results(self, job_id: str, **kwargs: Any) -> JobResults:
        """Will be overridden by the actual client class."""

    async def create_execution_request(
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
            ClientError: if an error occurs
        """
        process_description = await self.get_process(process_id)
        return ExecutionRequest.from_process_description(
            process_description, dotpath=dotpath
        )

    async def list_job_result_resources(
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

        Uses the same pipeline and views as ``Client.list_job_result_resources``.
        Await API retrieval and bounded metadata discovery; selection, iteration,
        and rendering on the returned snapshot remain local synchronous actions.
        Checks job status once without polling. Remote container traversal and
        continuation are not yet implemented.

        Args:
            job_id: Producing job identifier, never a resource URL.
            output_name: Original output to resolve; omit to include every output.
            parent_id: Exact loaded resource selector for immediate members.
            kind: Semantic kind filter, such as ``stac-item`` or ``asset``.
            data_type: Desired Python return type for opener candidate assessment.
            limits: Request, response, time, and expansion bounds.
            refresh: Discard cached metadata and failures before this listing.

        Returns:
            A portable listing with assessed opener candidates and output states.

        Raises:
            JobResultStatusError: The job has not completed successfully.
            ResourceNotFoundError: The output or loaded parent selector is absent.
            ClientError: Processing API retrieval failed.
            TypeError: Listing arguments are invalid.
        """
        _validate_listing_arguments(
            job_id, output_name, parent_id, kind, data_type, limits, refresh
        )
        self._require_open()
        self._bind_loop()
        async with self._job_result_lock:
            job = await self.get_job(job_id)
            if job.status != JobStatus.successful:
                raise JobResultStatusError(job)
            results = await self.get_job_results(job_id)
            process = None
            if job.processID:
                try:
                    process = await self.get_process(job.processID)
                except ClientError:
                    warnings.warn(
                        "Process description unavailable during resource discovery",
                        ClientWarning,
                        stacklevel=2,
                    )
            context = self._job_result_context(
                job_id, limits=limits, data_type=data_type, refresh=refresh
            )
            return await list_job_result_resources(
                context,
                results,
                process,
                output_name=output_name,
                parent_id=parent_id,
                kind=kind,
            )

    @overload
    async def open_job_result(
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
    async def open_job_result(
        self,
        job_id: JobResultResource,
        *,
        data_type: type | None = None,
        media_type: str | None = None,
        **options: Any,
    ) -> Any: ...

    async def open_job_result(
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
        self._bind_loop()
        context = JobResultContext(
            config=self.config,
            data_type=data_type,
            media_type=media_type,
            options=options,
        )
        if isinstance(job_id, JobResultResource):
            return await open_job_result(
                job_id,
                *self.config.get_job_result_opener_registry().opener_types,
                context=context,
            )
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            job_info = await self.get_job(job_id)
            if job_info.status not in (JobStatus.accepted, JobStatus.running):
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(
                    f"Cannot open result of job #{job_id}; "
                    f"it did not finish within {timeout} seconds"
                )
            await asyncio.sleep(poll_interval)
        if job_info.status != JobStatus.successful:
            raise JobResultStatusError(job_info)
        job_results = await self.get_job_results(job_id)
        process_id = job_info.processID
        process_description: ProcessDescription | None = None
        if process_id:
            try:
                process_description = await self.get_process(process_id)
            except ClientError:
                warnings.warn(
                    "An error occurred while getting process "
                    f"description for process ID {process_id!r}",
                    category=ClientWarning,
                    stacklevel=2,
                )
        resource = await describe_job_output(
            job_id,
            job_results,
            output_name,
            service_url=self.config.api_url,
            process_description=process_description,
            context=context,
        )
        opener_registry = self.config.get_job_result_opener_registry()
        return await open_job_result(
            resource, *opener_registry.opener_types, context=context
        )
