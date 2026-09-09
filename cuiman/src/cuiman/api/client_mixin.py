#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import time
import warnings
from abc import ABC, abstractmethod
from copy import deepcopy
from functools import partial
from typing import TYPE_CHECKING, Any

from authlib.integrations.httpx_client import OAuth2Client

from gavicore.models import JobInfo, JobResults, JobStatus, ProcessDescription
from gavicore.util.request import ExecutionRequest
from gavicore.util.runsync import run_sync

from .auth import client_credentials
from .auth.config import OAuth2AuthConfig
from .auth.session import LoginRequiredError, resolve_auth_headers
from .config import ClientConfig
from .defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from .exceptions import ClientError, ClientWarning
from .opener import JobResultOpenContext, JobResultStatusError
from .opener.opener import open_job_result
from .transport import Transport
from .transport.httpx2 import Httpx2Transport

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

    def _init_client_runtime(self) -> None:
        self._oauth_client: OAuth2Client | None = None

    @property
    def token(self) -> dict[str, Any] | None:
        """Return an independent snapshot of the live client-credentials token.

        Reading this property never starts authentication. Other authentication
        mechanisms currently retain their configuration-based token interface.
        """
        return (
            deepcopy(dict(self._oauth_client.token))
            if self._oauth_client and self._oauth_client.token
            else None
        )

    def close(self) -> None:
        """Close the transport and authentication runtime, including login-only use."""
        transport, self._transport = self._transport, None
        oauth_client, self._oauth_client = self._oauth_client, None
        try:
            if transport is not None:
                transport.close()
        finally:
            if oauth_client is not None:
                oauth_client.close()

    def _login_client_credentials(self, *, force: bool = False) -> dict[str, str]:
        auth = self.config.auth
        assert isinstance(auth, OAuth2AuthConfig)
        if self._oauth_client is None:
            self._oauth_client = client_credentials.create_client(auth)
        if force or not self._oauth_client.token:
            if not auth.client_id or not auth.client_secret:
                raise LoginRequiredError(
                    "Client credentials require client_id and client_secret. "
                    "Provide them through environment variables or Python configuration before client.login()."
                )
            self._oauth_client.fetch_token()
        client_credentials.save_token(auth, self._oauth_client.token)
        return {}

    def login(
        self, *, interactive: bool = True, no_browser: bool = False, force: bool = False
    ) -> None:
        """Prepare authentication, reusing existing credentials when possible.

        Explicit login may prompt for credentials or open an OIDC browser.
        API methods call this with ``interactive=False`` and raise a
        ``LoginRequiredError`` when user interaction is needed.
        Use ``force=True`` to bypass existing tokens and authenticate afresh.
        A successful login also updates an existing HTTPX2 transport.
        """
        if (
            isinstance(self.config.auth, OAuth2AuthConfig)
            and self.config.auth.grant_type == "client_credentials"
        ):
            self._login_client_credentials(force=force)
            return
        headers = resolve_auth_headers(
            self.config.auth,
            interactive=interactive,
            no_browser=no_browser,
            force=force,
        )
        if self._transport is not None and isinstance(self._transport, Httpx2Transport):
            self._transport.headers = headers

    def _get_transport(self) -> Transport:
        if self._transport is None:
            if self._oauth_client is None or not self._oauth_client.token:
                self.login(interactive=False)
            assert self.config.api_url is not None
            if self._oauth_client is not None:
                auth = self.config.auth
                assert isinstance(auth, OAuth2AuthConfig)

                self._transport = Httpx2Transport(
                    api_url=f"{self.config.api_url.rstrip('/')}/",
                    sync_httpx2=self._oauth_client,
                    return_type_map=self.config.return_type_map,
                    token_refresher=partial(self._login_client_credentials, force=True),
                    debug=self._debug,
                    auth_header=(
                        "Authorization" if auth.use_bearer else auth.access_token_header
                    ),
                )
                return self._transport
            self._transport = Httpx2Transport(
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
