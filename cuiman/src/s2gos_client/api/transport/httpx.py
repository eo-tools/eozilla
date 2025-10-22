#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging
from typing import Any

import httpx

from s2gos_client.api.exceptions import ClientError
from s2gos_common.models import ApiError

from .args import TransportArgs
from .transport import AsyncTransport, Transport, TransportError


class HttpxTransport(Transport, AsyncTransport):
    """A concrete web API transport based on the httpx package."""

    def __init__(self, server_url: str, debug: bool = False):
        self.server_url = server_url
        self.debug = debug
        self.sync_httpx: httpx.Client | None = None
        self.async_httpx: httpx.AsyncClient | None = None
        # Note, by default, we silence the httpx logger, however it may be
        #   useful to make that configurable
        logging.getLogger("httpx").setLevel(
            logging.DEBUG if debug else logging.CRITICAL
        )

    def call(self, args: TransportArgs) -> Any:
        if self.sync_httpx is None:
            self.sync_httpx = httpx.Client()
        args_, kwargs_ = self._get_request_args(args)
        try:
            response = self.sync_httpx.request(*args_, **kwargs_)
        except httpx.HTTPError as e:
            raise TransportError(f"{e}") from e
        return self._process_response(args, response)

    async def async_call(self, args: TransportArgs) -> Any:
        if self.async_httpx is None:
            self.async_httpx = httpx.AsyncClient()
        args_, kwargs_ = self._get_request_args(args)
        try:
            response = await self.async_httpx.request(*args_, **kwargs_)
        except httpx.HTTPError as e:
            raise TransportError(f"{e}") from e
        return self._process_response(args, response)

    def _get_request_args(
        self, args: TransportArgs
    ) -> tuple[tuple[str, str], dict[str, Any]]:
        url = args.get_url(self.server_url)
        request_json = args.get_json_for_request()
        return (args.method.upper(), url), {
            "params": args.query_params,
            "json": request_json,
            **args.extra_kwargs,
        }

    # noinspection PyMethodMayBeStatic
    def _process_response(self, args: TransportArgs, response: httpx.Response) -> Any:
        try:
            # Note, actually we should only do `response.json()` if JSON is expected,
            # use args.return_types for this decision.
            response_json = response.json()
        except (ValueError, TypeError) as e:
            raise ClientError(
                f"{e}",
                api_error=ApiError(
                    type=type(e).__name__,
                    title="Expected JSON response from API",
                    detail=f"{e}",
                ),
            ) from e
        try:
            response.raise_for_status()
            return args.get_response_for_status(response.status_code, response_json)
        except httpx.HTTPError as e:
            raise args.get_exception_for_status(
                response.status_code, f"{e}", response_json
            ) from e

    def close(self):
        if self.sync_httpx is not None:
            assert self.async_httpx is None
            self.sync_httpx.close()
            self.sync_httpx = None

    async def async_close(self):
        if self.async_httpx is not None:
            assert self.sync_httpx is None
            await self.async_httpx.aclose()
            self.async_httpx = None
