#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Developer contexts and shared, bounded metadata loading for discovery."""

import asyncio
import json
import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Protocol

from gavicore.models import OutputDescription, ProcessDescription


@dataclass(frozen=True)
class DiscoveryLimits:
    """Initial discovery limits, shared by a resolver and its transformations."""

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
    """A bounded response supplied by a runtime metadata fetch adapter."""

    content: bytes
    """JSON metadata bytes; the fetcher must stop at the requested size limit."""
    url: str
    """Actual document URI, including any redirects, used as its reference base."""
    media_type: str | None = None
    """Advertised response Content-Type, retaining its parameters."""


class MetadataFetcher(Protocol):
    """Runtime metadata I/O; implementations own sessions and scoped authentication."""

    async def __call__(
        self, href: str, *, max_bytes: int, timeout: float
    ) -> MetadataResponse:
        """Read at most ``max_bytes`` of metadata, never an Asset payload."""
        ...


@dataclass(frozen=True)
class MetadataDocument:
    """Parsed metadata returned as an independent snapshot from the loader."""

    value: Any
    """Parsed JSON value; changing it does not change the cached document."""
    base_uri: str
    """Containing document's effective URI for resolving relative references."""
    media_type: str | None
    """Response media type, when advertised."""


class DiscoveryError(Exception):
    """A discovery failure with a non-secret, portable explanation."""

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
    """Share cached metadata and fetch budgets across resolver delegation.

    Fetch adapters receive explicit size/time limits and must bound their reads.
    The loader also checks the returned size, parses JSON once, caches successes
    and failures, and propagates cancellation. No Asset access service is used.
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
        """Number of metadata fetch attempts, excluding cache hits."""
        return self._requests

    async def load(self, href: str) -> MetadataDocument:
        """Load bounded JSON metadata once, returning an independent snapshot."""
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
        """Discard cached metadata and failures and reset the request budget.

        Call between operations for an explicit refresh, never during a load.
        Transformation results are not cached by this loader.
        """
        self._cache.clear()
        self._requests = 0


@dataclass(frozen=True)
class ResolutionContext:
    """Original output, provenance, and shared discovery services for extensions.

    Every output value is passed here unchanged, including qualified wrappers.
    Resolvers may inspect but must not mutate source values or process metadata.
    A composed resolver delegates with this same context and loader. Ordinary
    client callers will not need to construct developer contexts.
    """

    output_name: str
    """Original process output identifier; retained by all derived resources."""
    value: Any
    """Original Link, qualified value, or arbitrary inline output value."""
    job_id: str | None = None
    """Producing job identity, when supplied by the client."""
    service_url: str | None = None
    """Producing service identity; never an authorization to forward credentials."""
    base_uri: str | None = None
    """Containing result document URI for relative output references."""
    output_description: OutputDescription | None = None
    """Original output/schema description, used for detection and provenance."""
    process_description: ProcessDescription | None = None
    """Producing process description, available for process-scoped acceptance."""
    loader: MetadataLoader | None = None
    """Shared bounded metadata loader; absent for purely inline discovery."""
    limits: DiscoveryLimits = field(default_factory=DiscoveryLimits)
    """Discovery limits; a supplied loader's limits take precedence."""
    stac_hint: bool = False
    """Explicit STAC candidate hint permitting a bounded metadata probe."""

    def __post_init__(self) -> None:
        if not self.output_name:
            raise ValueError("An output name is required")
        if self.loader is not None:
            object.__setattr__(self, "limits", self.loader.limits)


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-JSON constant: {value}")
