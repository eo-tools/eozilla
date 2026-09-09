#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging
from typing import Any, Awaitable, Callable

import httpx2

from cuiman.api.exceptions import ClientError
from gavicore.models import ApiError

from .args import CLIENT_ERROR_URI, TransportArgs
from .transport import AsyncTransport, Transport, TransportError


class Httpx2Transport(Transport, AsyncTransport):
    """A concrete web API transport based on the httpx2 package."""

    def __init__(
        self,
        api_url: str,
        headers: dict[str, str] | None = None,
        return_type_map: dict[type, type] | None = None,
        token_refresher: Callable[[], dict[str, str]] | None = None,
        async_token_refresher: (Callable[[], Awaitable[dict[str, str]]] | None) = None,
        debug: bool = False,
        *,
        sync_httpx2: httpx2.Client | None = None,
        async_httpx2: httpx2.AsyncClient | None = None,
        auth_header: str | None = None,
    ):
        self.api_url = api_url
        self.headers = headers
        self.return_type_map = return_type_map or {}
        self.token_refresher = token_refresher
        self.async_token_refresher = async_token_refresher
        self.debug = debug
        self.sync_httpx2 = sync_httpx2
        self.async_httpx2 = async_httpx2
        self.auth_header = auth_header
        self._owns_http_client = sync_httpx2 is None and async_httpx2 is None
        # Note, by default, we silence the httpx2 logger, however it may be
        #   useful to make that configurable
        logging.getLogger("httpx2").setLevel(
            logging.DEBUG if debug else logging.CRITICAL
        )

    def call(self, args: TransportArgs) -> Any:
        if self.sync_httpx2 is None:
            self.sync_httpx2 = httpx2.Client()
        response = self._sync_request(args)
        if (
            response.status_code == 401
            and self.token_refresher is not None
            and not self._auth_overridden(args)
        ):
            self.headers = self.token_refresher()
            response = self._sync_request(args)
        return self._process_response(args, response)

    async def async_call(self, args: TransportArgs) -> Any:
        if self.async_httpx2 is None:
            self.async_httpx2 = httpx2.AsyncClient()
        response = await self._async_request(args)
        if (
            response.status_code == 401
            and self.async_token_refresher is not None
            and not self._auth_overridden(args)
        ):
            self.headers = await self.async_token_refresher()
            response = await self._async_request(args)
        return self._process_response(args, response)

    def _sync_request(self, args: TransportArgs) -> httpx2.Response:
        assert self.sync_httpx2 is not None
        args_, kwargs_ = self._get_request_args(args)
        try:
            return self.sync_httpx2.request(*args_, **kwargs_)
        except httpx2.HTTPError as e:
            raise TransportError(f"{e}") from e

    async def _async_request(self, args: TransportArgs) -> httpx2.Response:
        assert self.async_httpx2 is not None
        args_, kwargs_ = self._get_request_args(args)
        try:
            return await self.async_httpx2.request(*args_, **kwargs_)
        except httpx2.HTTPError as e:
            raise TransportError(f"{e}") from e

    def _get_request_args(
        self, args: TransportArgs
    ) -> tuple[tuple[str, str], dict[str, Any]]:
        url = args.get_url(self.api_url)
        request_json = args.get_json_for_request()
        extra_kwargs = args.extra_kwargs
        if self.auth_header and self._auth_overridden(args):
            extra_kwargs = dict(extra_kwargs)
            extra_kwargs.setdefault("auth", None)
        if self.headers:
            extra_kwargs = dict(extra_kwargs)
            headers = dict(self.headers)
            headers.update(extra_kwargs.pop("headers", {}))
            extra_kwargs["headers"] = headers
        return (args.method.upper(), url), {
            "params": args.query_params,
            "json": request_json,
            **extra_kwargs,
        }

    def _auth_overridden(self, args: TransportArgs) -> bool:
        if self.auth_header is None:
            return False
        return "auth" in args.extra_kwargs or self.auth_header in httpx2.Headers(
            args.extra_kwargs.get("headers")
        )

    # noinspection PyMethodMayBeStatic
    def _process_response(self, args: TransportArgs, response: httpx2.Response) -> Any:
        try:
            # Note, actually we should only do `response.json()` if JSON is expected,
            # use args.return_types for this decision.
            response_json = response.json()
        except (ValueError, TypeError) as e:
            message = "Expected JSON response from API"
            raise ClientError(
                message,
                api_error=ApiError(
                    type=CLIENT_ERROR_URI,
                    instance=args.path,
                    status=response.status_code,
                    title=message,
                    detail=str(e),
                ),
            ) from e
        try:
            response.raise_for_status()
            return args.get_response_for_status(
                response.status_code, response_json, self.return_type_map
            )
        except httpx2.HTTPError as e:
            raise args.get_exception_for_status(
                response.status_code,
                response_json,
                f"{e}",
            ) from e

    def close(self):
        if self.sync_httpx2 is not None:
            assert self.async_httpx2 is None
            if self._owns_http_client:
                self.sync_httpx2.close()
            self.sync_httpx2 = None

    async def async_close(self):
        if self.async_httpx2 is not None:
            assert self.sync_httpx2 is None
            if self._owns_http_client:
                await self.async_httpx2.aclose()
            self.async_httpx2 = None
