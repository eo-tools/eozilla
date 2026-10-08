# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License.

import asyncio
import copy
import math
import os
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import url2pathname

import httpx2

from .errors import StacJobResultOpenError


class StacMetadataIO:
    """Bounded metadata reads with explicit host-scoped headers and no API auth.

    One instance represents one opening operation. Application factories may
    supply headers keyed by absolute HTTP origins and fresh HTTP transports.
    These runtime objects and credentials never enter STAC serialization.
    """

    def __init__(
        self,
        *,
        max_bytes: int = 2 * 1024 * 1024,
        timeout: float = 10.0,
        max_requests: int = 16,
        headers_by_origin: Mapping[str, Mapping[str, str]] | None = None,
        sync_transport_factory: Callable[[], httpx2.BaseTransport] | None = None,
        async_transport_factory: Callable[[], httpx2.AsyncBaseTransport] | None = None,
    ):
        if (
            max_bytes <= 0
            or timeout <= 0
            or not math.isfinite(timeout)
            or max_requests <= 0
        ):
            raise ValueError("STAC metadata limits must be positive")
        self.max_bytes = max_bytes
        """Maximum decoded response bytes per metadata document."""
        self.timeout = timeout
        """Per-fetch timeout in seconds, including redirects and streaming."""
        self.max_requests = max_requests
        """Maximum metadata requests in this operation, including redirects."""
        self._headers = {
            _origin(origin): dict(headers)
            for origin, headers in (headers_by_origin or {}).items()
        }
        self._sync_transport_factory = sync_transport_factory
        self._async_transport_factory = async_transport_factory
        self._cache: dict[str, tuple[str, str]] = {}
        self._requests = 0

    def new_operation(self) -> "StacMetadataIO":
        """Retain application policy while starting fresh budgets and caches.

        Explicit native navigation uses a new operation for each document;
        initial-opening budgets are not a promise about an entire remote crawl.
        """
        result = copy.copy(self)
        result._cache = {}
        result._requests = 0
        return result

    def read_text_with_href(self, source: str) -> tuple[str, str]:
        """Read bounded UTF-8 metadata and return its effective containing URI."""
        if source in self._cache:
            return self._cache[source]
        try:
            if _is_http(source):
                result = self._read_http(source)
            else:
                self._consume_request()
                result = self._read_file(source, threading.Event())
        except StacJobResultOpenError:
            raise
        except Exception as error:
            raise StacJobResultOpenError(
                f"STAC metadata read failed ({type(error).__name__})"
            ) from None
        self._cache[source] = result
        self._cache[result[1]] = result
        return result

    async def async_read_text_with_href(self, source: str) -> tuple[str, str]:
        """Read metadata without blocking the event loop; propagate cancellation."""
        if source in self._cache:
            return self._cache[source]
        stop = threading.Event()
        try:
            async with asyncio.timeout(self.timeout):
                if _is_http(source):
                    result = await self._async_read_http(source)
                else:
                    self._consume_request()
                    result = await asyncio.to_thread(self._read_file, source, stop)
        except StacJobResultOpenError:
            raise
        except TimeoutError:
            raise StacJobResultOpenError("STAC metadata fetch timed out") from None
        except Exception as error:
            raise StacJobResultOpenError(
                f"STAC metadata read failed ({type(error).__name__})"
            ) from None
        finally:
            stop.set()
        self._cache[source] = result
        self._cache[result[1]] = result
        return result

    def _consume_request(self) -> None:
        if self._requests >= self.max_requests:
            raise StacJobResultOpenError("STAC metadata request limit exceeded")
        self._requests += 1

    def _check_deadline(self, deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StacJobResultOpenError("STAC metadata fetch timed out")
        return remaining

    def _append(self, data: bytearray, chunk: bytes) -> None:
        if len(data) + len(chunk) > self.max_bytes:
            raise StacJobResultOpenError("STAC metadata byte limit exceeded")
        data.extend(chunk)

    def _read_file(self, source: str, stop: threading.Event) -> tuple[str, str]:
        path = _local_path(source)
        deadline = time.monotonic() + self.timeout
        data = bytearray()
        with path.open("rb") as stream:
            while True:
                self._check_deadline(deadline)
                if stop.is_set():
                    raise StacJobResultOpenError("STAC metadata file read cancelled")
                chunk = stream.read(min(65536, self.max_bytes - len(data) + 1))
                if not chunk:
                    break
                self._append(data, chunk)
        self._check_deadline(deadline)
        return data.decode("utf-8"), path.resolve().as_uri()

    def _read_http(self, source: str) -> tuple[str, str]:
        deadline = time.monotonic() + self.timeout
        transport = (
            self._sync_transport_factory() if self._sync_transport_factory else None
        )
        with httpx2.Client(
            transport=transport, trust_env=False, follow_redirects=False
        ) as client:
            href = source
            while True:
                self._consume_request()
                client.cookies.clear()
                timeout = self._check_deadline(deadline)
                with client.stream(
                    "GET",
                    href,
                    headers=self._headers.get(_origin(href), {}),
                    timeout=timeout,
                ) as response:
                    if response.is_redirect:
                        href = urljoin(str(response.url), response.headers["location"])
                        _origin(href)
                        continue
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        self._check_deadline(deadline)
                        self._append(data, chunk)
                    self._check_deadline(deadline)
                    return data.decode("utf-8"), str(response.url)

    async def _async_read_http(self, source: str) -> tuple[str, str]:
        transport = (
            self._async_transport_factory() if self._async_transport_factory else None
        )
        async with httpx2.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False
        ) as client:
            href = source
            while True:
                self._consume_request()
                client.cookies.clear()
                async with client.stream(
                    "GET",
                    href,
                    headers=self._headers.get(_origin(href), {}),
                    timeout=self.timeout,
                ) as response:
                    if response.is_redirect:
                        href = urljoin(str(response.url), response.headers["location"])
                        _origin(href)
                        continue
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        self._append(data, chunk)
                    return data.decode("utf-8"), str(response.url)


def _origin(href: str) -> tuple[str, str, int]:
    parsed = urlsplit(href)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise StacJobResultOpenError("STAC metadata HTTP origin is unsupported")
    return (
        parsed.scheme,
        parsed.hostname.lower(),
        parsed.port
        if parsed.port is not None
        else (443 if parsed.scheme == "https" else 80),
    )


def _is_http(source: str) -> bool:
    return urlsplit(source).scheme.lower() in ("http", "https")


def _local_path(source: str) -> Path:
    parsed = urlsplit(source)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc != "localhost":
            if os.name != "nt":
                raise StacJobResultOpenError(
                    "Remote file URI is unsupported on this platform"
                )
            return Path(f"//{parsed.netloc}{url2pathname(parsed.path)}")
        return Path(url2pathname(parsed.path))
    if parsed.scheme and not (os.name == "nt" and len(parsed.scheme) == 1):
        raise StacJobResultOpenError("STAC metadata URI scheme is unsupported")
    return Path(source)
