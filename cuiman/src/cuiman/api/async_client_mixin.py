#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import threading
import warnings
from abc import abstractmethod
from typing import Any

import httpx2
from authlib.integrations.httpx_client import AsyncOAuth2Client

from gavicore.models import JobInfo, JobResults, JobStatus, ProcessDescription
from gavicore.util.request import ExecutionRequest

from .auth.config import OidcAuthConfig
from .auth.interactive import authorize
from .auth.oidc import LoopbackCallbackServer
from .client_mixin_base import ClientMixinBase
from .defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from .exceptions import ClientError, ClientWarning
from .opener import JobResultOpenContext, JobResultStatusError
from .opener.opener import open_job_result
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
            self._closed = True
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
        self._require_open()
        try:
            async with self._runtime_lock:
                self._require_open()
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
                await self.close()

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

    async def open_job_result(
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
        return await open_job_result(ctx, *opener_registry.opener_types)
