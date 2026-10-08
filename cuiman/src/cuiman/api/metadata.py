#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Fetch and parse JSON descriptions so resolvers can discover linked resources.

``MetadataFetcher`` reads bytes into a ``MetadataResponse``; ``MetadataLoader``
parses those bytes into a ``MetadataDocument`` and shares its cache and
``DiscoveryLimits`` across resolver calls. This keeps transport-specific details
out of resolvers and bounds discovery without reading the described data files.
"""

import asyncio
import json
import math
import ntpath
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit
from urllib.request import url2pathname

import httpx2


@dataclass(frozen=True)
class DiscoveryLimits:
    """Bound the work needed to turn job outputs into resource descriptions.

    A shared set of limits prevents delegated resolvers and transformers from
    each starting a fresh budget. The loader enforces request, byte, and time
    limits; resolvers and transformers enforce expansion limits.
    """

    max_requests: int = 16
    """Maximum metadata fetch attempts within one loader operation."""
    max_bytes: int = 2 * 1024 * 1024
    """Maximum bytes in one metadata response."""
    max_items: int = 100
    """Maximum embedded STAC Items resolved from one document."""
    max_resources: int = 1000
    """Maximum flat resources produced by a resolution or transformation stage."""
    max_depth: int = 8
    """Maximum ancestry depth of declared or explicitly traversed descendants."""
    timeout: float = 10.0
    """Maximum seconds for one metadata fetch."""

    def __post_init__(self) -> None:
        if (
            min(
                self.max_requests,
                self.max_bytes,
                self.max_items,
                self.max_resources,
                self.max_depth,
            )
            < 1
        ):
            raise ValueError("Discovery count and size limits must be positive")
        if self.timeout <= 0 or not math.isfinite(self.timeout):
            raise ValueError("Discovery timeout must be positive")


@dataclass(frozen=True)
class MetadataResponse:
    """Metadata bytes and their source information returned by a fetcher.

    This is the handoff from transport-specific fetching to JSON parsing in
    ``MetadataLoader``. The effective URL preserves the base for relative links
    after redirects; the media type preserves the server's format description.
    The fetcher must bound its read before constructing this response.
    """

    content: bytes
    """JSON metadata bytes; the fetcher must stop at the requested size limit."""
    url: str
    """Actual document URI, including any redirects, used as its reference base."""
    media_type: str | None = None
    """Advertised response Content-Type, retaining its parameters."""


class MetadataFetcher(Protocol):
    """Supply metadata reads to the loader using the application's transport.

    This callable contract lets discovery use an existing HTTP session, local
    files, or a test fetcher without embedding those choices in resolvers.
    Implementations own sessions and authentication scoped to the metadata URL;
    they must enforce the supplied byte and time limits while reading.
    """

    async def __call__(
        self, href: str, *, max_bytes: int, timeout: float
    ) -> MetadataResponse:
        """Read metadata within ``max_bytes`` and ``timeout`` for JSON discovery.

        Return the effective URL so the loader can retain the document's base.
        This operation fetches a description, never an Asset's data payload.
        """
        ...


@dataclass(frozen=True)
class MetadataDocument:
    """Parsed JSON and its reference base, ready for a resolver to inspect.

    Unlike ``MetadataResponse``, this contains a Python value rather than bytes.
    The loader returns an independent copy so a resolver cannot change cached
    metadata seen by another resolver; ``base_uri`` travels with the value so
    relative Asset and navigation links keep their meaning.
    """

    value: Any
    """Parsed JSON value; changing it does not change the cached document."""
    base_uri: str
    """Containing document's effective URI for resolving relative references."""
    media_type: str | None
    """Response media type, when advertised."""


class DiscoveryError(Exception):
    """Carry a discovery failure that can become a resource diagnostic.

    The code and non-secret message let callers report failures without copying
    transport exception text, which may contain credentials. ``partial`` marks
    a limit that stopped discovery while leaving an incomplete view usable.
    """

    code: str
    """Machine-readable failure identifier."""
    message: str
    """Non-secret explanation suitable for a portable diagnostic."""
    partial: bool
    """Whether discovery stopped at a limit rather than failing outright."""

    def __init__(self, code: str, message: str, *, partial: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.partial = partial


class MetadataLoader:
    """Load JSON descriptions once for cooperating resolvers and transformers.

    Acceptance and resolution can inspect the same linked document without
    fetching it twice or each consuming a separate request budget. The supplied
    fetcher handles transport; this loader checks response size, parses JSON,
    caches successes and failures, and returns independent document copies.
    It also enforces timeouts and propagates cancellation. Asset credentials
    and data reading belong to opening, outside this loader.
    """

    limits: DiscoveryLimits
    """Shared request, response, and expansion limits."""

    def __init__(self, fetch: MetadataFetcher, limits: DiscoveryLimits | None = None):
        self.limits = limits or DiscoveryLimits()
        self._fetch = fetch
        self._requests = 0
        self._cache: dict[str, MetadataDocument | DiscoveryError] = {}
        self._lock = asyncio.Lock()

    @property
    def request_count(self) -> int:
        """Count fetch attempts to inspect consumption of the shared request budget.

        Cache hits do not consume requests; failed fetch attempts do.
        """
        return self._requests

    async def load(self, href: str) -> MetadataDocument:
        """Return parsed metadata for recognition or resource expansion.

        Reuse cached documents and failures for this URL so acceptance and
        resolution share the same fetch. Each successful call returns an
        independent copy. Raise ``DiscoveryError`` for limits, invalid JSON,
        or fetching failures, leaving reporting to the discovery caller.
        """
        async with self._lock:
            cached = self._cache.get(href)
            if isinstance(cached, DiscoveryError):
                raise cached
            if cached is not None:
                return deepcopy(cached)
            if self._requests >= self.limits.max_requests:
                raise DiscoveryError(
                    "request-limit", "Metadata request budget reached", partial=True
                )
            self._requests += 1
            try:
                response = await asyncio.wait_for(
                    self._fetch(
                        href,
                        max_bytes=self.limits.max_bytes,
                        timeout=self.limits.timeout,
                    ),
                    self.limits.timeout,
                )
                if len(response.content) > self.limits.max_bytes:
                    raise DiscoveryError(
                        "byte-limit",
                        "Metadata response size limit reached",
                        partial=True,
                    )
                try:
                    value = json.loads(
                        response.content, parse_constant=_invalid_constant
                    )
                except (ValueError, UnicodeError) as exc:
                    raise DiscoveryError(
                        "invalid-json", "Referenced metadata is not valid JSON"
                    ) from exc
                document = MetadataDocument(value, response.url, response.media_type)
                self._cache[href] = document
                return deepcopy(document)
            except DiscoveryError as exc:
                self._cache[href] = exc
                raise
            except Exception as exc:
                error = DiscoveryError(
                    "metadata-access", f"Metadata fetch failed ({type(exc).__name__})"
                )
                self._cache[href] = error
                raise error from exc

    def clear(self) -> None:
        """Start fresh discovery by clearing documents, failures, and request usage.

        Call between operations for an explicit refresh, never during a load.
        Transformation results are not cached by this loader.
        """
        self._cache.clear()
        self._requests = 0

    def for_operation(self) -> "MetadataLoader":
        """Reuse cached documents in a new operation with fresh request limits.

        Clients use this between listings so each request has its own budget and
        async lock, including when synchronous calls run on different event loops.
        Copies isolate cached values and failures from the preceding operation.
        Retain at most one request budget's most recent entries so repeated
        listings of changing metadata URLs cannot grow the cache indefinitely.
        """
        loader = MetadataLoader(self._fetch, self.limits)
        loader._cache = {
            href: DiscoveryError(value.code, value.message, partial=value.partial)
            if isinstance(value, DiscoveryError)
            else deepcopy(value)
            for href, value in list(self._cache.items())[-self.limits.max_requests :]
        }
        return loader


async def fetch_metadata(
    href: str, *, max_bytes: int, timeout: float
) -> MetadataResponse:
    """Read bounded metadata using unauthenticated HTTP or a local file.

    This is the client's default transport for JSON discovery. HTTP redirects
    retain their effective URL and reads stop at the byte limit. Processing API
    credentials and Asset access providers are not used. Applications requiring
    another transport or scoped authentication configure a ``MetadataFetcher``.
    """
    if ntpath.isabs(href) or href.startswith("/"):
        path = Path(href)
    else:
        url = urlsplit(href)
        if url.scheme in {"http", "https"}:
            async with httpx2.AsyncClient(follow_redirects=True) as client:
                async with client.stream("GET", href, timeout=timeout) as response:
                    response.raise_for_status()
                    http_content = bytearray()
                    async for chunk in response.aiter_bytes(
                        chunk_size=min(max_bytes + 1, 65536)
                    ):
                        if len(http_content) + len(chunk) > max_bytes:
                            raise DiscoveryError(
                                "byte-limit",
                                "Metadata response size limit reached",
                                partial=True,
                            )
                        http_content.extend(chunk)
                    return MetadataResponse(
                        bytes(http_content),
                        str(response.url),
                        response.headers.get("content-type"),
                    )
        if url.scheme != "file" or url.netloc not in {"", "localhost"}:
            raise DiscoveryError(
                "metadata-scheme", "Metadata location requires a configured fetcher"
            )
        path = Path(url2pathname(url.path))
    content = await asyncio.wait_for(
        asyncio.to_thread(_read_metadata_file, path, max_bytes), timeout
    )
    return MetadataResponse(content, path.resolve().as_uri())


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-JSON constant: {value}")


def _read_metadata_file(path: Path, max_bytes: int) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(max_bytes)
        if stream.read(1):
            raise DiscoveryError(
                "byte-limit", "Metadata response size limit reached", partial=True
            )
    return content
