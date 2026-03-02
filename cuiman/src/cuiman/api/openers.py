#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import httpx

from gavicore.models import (
    InlineOrRefValue,
    InlineValue,
    JobResults,
    Link,
    ProcessDescription,
    QualifiedValue,
)


class SyncResultClient(Protocol):
    """Protocol consumed by result openers."""

    @property
    def config(self) -> Any:
        """Client configuration with optional auth headers."""


@dataclass(frozen=True)
class OpenJobResultContext:
    """Context passed to opener callables."""

    client: SyncResultClient
    job_results: JobResults
    output_name: Optional[str]
    output_value: Any
    output_entry: Optional[InlineOrRefValue]
    process_description: Optional[ProcessDescription]
    data_type: str
    options: dict[str, Any]

    @property
    def output_link(self) -> Optional[Link]:
        if isinstance(self.output_value, Link):
            return self.output_value
        return None

    @property
    def media_type(self) -> Optional[str]:
        if isinstance(self.output_value, Link):
            return self.output_value.type
        if isinstance(self.output_value, QualifiedValue) and self.output_value.mediaType:
            return self.output_value.mediaType
        return self.options.get("media_type")


def _extract_output_value(output_entry: InlineOrRefValue) -> Any:
    output_value = output_entry.root
    if isinstance(output_value, QualifiedValue):
        return output_value.value.root
    if isinstance(output_value, InlineValue):
        return output_value.root
    return output_value


def _find_default_output_name(job_results: JobResults, output_name: Optional[str]) -> Optional[str]:
    if output_name:
        return output_name
    outputs = job_results.root or {}
    if len(outputs) == 1:
        return next(iter(outputs.keys()))
    return None


def infer_data_type(
    output_value: Any,
    *,
    output_entry: Optional[InlineOrRefValue],
    process_description: Optional[ProcessDescription],
    output_name: Optional[str],
    options: dict[str, Any],
) -> str:
    """Infer a default data type from job output metadata."""
    declared_data_type = options.get("data_type")
    if declared_data_type:
        return str(declared_data_type)

    media_type = options.get("media_type")
    if not media_type and isinstance(output_value, Link):
        media_type = output_value.type
    if not media_type and isinstance(output_entry, InlineOrRefValue):
        entry_root = output_entry.root
        if isinstance(entry_root, QualifiedValue) and entry_root.mediaType:
            media_type = entry_root.mediaType

    if isinstance(media_type, str):
        media_type_lc = media_type.lower()
        if "json" in media_type_lc:
            return "json"
        if media_type_lc.startswith("text/"):
            return "text"
        if "netcdf" in media_type_lc:
            return "netcdf"
        if "geotiff" in media_type_lc or "tiff" in media_type_lc:
            return "geotiff"

    if process_description and output_name and process_description.outputs:
        output_description = process_description.outputs.get(output_name)
        if output_description and output_description.schema_.format:
            return str(output_description.schema_.format)

    if isinstance(output_value, (dict, list)):
        return "json"
    if isinstance(output_value, str):
        return "text"
    if isinstance(output_value, bytes):
        return "bytes"
    if isinstance(output_value, Link):
        return "link"
    return "raw"


Opener = Callable[[OpenJobResultContext], Any]
OpenerMatcher = Callable[[OpenJobResultContext], bool]


class JobResultOpenerRegistry:
    """Registry for opening `JobResults` values in extensible ways.

    The registry supports two dispatch mechanisms:

    1. Direct dispatch by `data_type` key via :meth:`register_data_type`.
    2. Predicate-based dispatch via :meth:`register_matcher`.

    If no explicit opener is found, the registry falls back to a `raw` opener
    when available.
    """

    def __init__(self):
        """Create an empty registry with no predefined openers."""
        self._openers: dict[str, Opener] = {}
        self._matchers: list[tuple[str, OpenerMatcher, Opener]] = []

    def register_data_type(self, data_type: str, opener: Opener) -> None:
        """Register an opener callable for a normalized data-type key.

        Args:
            data_type: Data type name used during opener dispatch.
            opener: Callable receiving an :class:`OpenJobResultContext`.
        """
        self._openers[data_type.lower()] = opener

    def register_matcher(self, name: str, matcher: OpenerMatcher, opener: Opener) -> None:
        """Register a predicate-based opener evaluated after type dispatch.

        Args:
            name: Human-readable matcher name for debugging/tracing.
            matcher: Predicate that decides if `opener` should be used.
            opener: Callable receiving an :class:`OpenJobResultContext`.
        """
        self._matchers.append((name, matcher, opener))

    def open(self, context: OpenJobResultContext) -> Any:
        """Open a job-result value from the given context.

        Dispatch order is: data-type opener, then registered matchers, then
        `raw` fallback opener.

        Args:
            context: Opening context containing output value and metadata.

        Returns:
            Value produced by the selected opener.

        Raises:
            ValueError: If no opener matches and no `raw` fallback exists.
        """
        opener = self._openers.get(context.data_type.lower())
        if opener is not None:
            return opener(context)
        for _name, matcher, matcher_opener in self._matchers:
            if matcher(context):
                return matcher_opener(context)
        fallback = self._openers.get("raw")
        if fallback is None:
            raise ValueError(f"No opener registered for data type {context.data_type!r}")
        return fallback(context)

    @classmethod
    def create_default(cls) -> JobResultOpenerRegistry:
        """Create a registry with built-in openers.

        The returned registry includes handlers for `raw`, `json`, `text`,
        `bytes`, and `link`.

        Returns:
            A registry pre-populated with default openers.
        """
        registry = cls()
        registry.register_data_type("raw", lambda context: context.output_value)
        registry.register_data_type("json", _open_json)
        registry.register_data_type("text", _open_text)
        registry.register_data_type("bytes", _open_bytes)
        registry.register_data_type("link", _open_link)
        return registry


def _open_link(context: OpenJobResultContext) -> Any:
    if isinstance(context.output_value, Link):
        return str(context.output_value.href)
    return context.output_value


def _fetch_link_content(context: OpenJobResultContext) -> httpx.Response:
    link = context.output_link
    if link is None:
        raise ValueError("Output value is not a link")

    headers = {}
    auth_headers = getattr(context.client.config, "auth_headers", None)
    if isinstance(auth_headers, dict):
        headers.update(auth_headers)
    extra_headers = context.options.get("headers")
    if isinstance(extra_headers, dict):
        headers.update(extra_headers)

    timeout = context.options.get("timeout", 30.0)
    return httpx.get(str(link.href), headers=headers, timeout=timeout)


def _open_json(context: OpenJobResultContext) -> Any:
    if isinstance(context.output_value, Link):
        response = _fetch_link_content(context)
        response.raise_for_status()
        return response.json()
    return context.output_value


def _open_text(context: OpenJobResultContext) -> Any:
    if isinstance(context.output_value, Link):
        response = _fetch_link_content(context)
        response.raise_for_status()
        return response.text
    return str(context.output_value)


def _open_bytes(context: OpenJobResultContext) -> Any:
    if isinstance(context.output_value, Link):
        response = _fetch_link_content(context)
        response.raise_for_status()
        return response.content
    if isinstance(context.output_value, bytes):
        return context.output_value
    return bytes(str(context.output_value), encoding="utf-8")


def build_open_job_result_context(
    *,
    client: SyncResultClient,
    job_results: JobResults,
    data_type: Optional[str],
    process_description: Optional[ProcessDescription],
    options: dict[str, Any],
) -> OpenJobResultContext:
    output_name = _find_default_output_name(job_results, options.get("output_name"))
    output_entry = (job_results.root or {}).get(output_name) if output_name else None
    output_value = _extract_output_value(output_entry) if output_entry else job_results.root
    inferred_data_type = data_type or infer_data_type(
        output_value,
        output_entry=output_entry,
        process_description=process_description,
        output_name=output_name,
        options=options,
    )

    return OpenJobResultContext(
        client=client,
        job_results=job_results,
        output_name=output_name,
        output_value=output_value,
        output_entry=output_entry,
        process_description=process_description,
        data_type=inferred_data_type,
        options=options,
    )
