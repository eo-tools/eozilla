# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Turn original job outputs into scoped, assessed resource listings for clients."""

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from typing import Any
from urllib.parse import quote, urlsplit

from gavicore.models import JobResults, ProcessDescription

from .context import JobResultContext
from .metadata import DiscoveryLimits
from .opener.opener import assess_job_result
from .resolver import resolve_job_result
from .resolver.resolver import json_value
from .resources import (
    DiscoveryState,
    JobResultResource,
    JobResultResourceListing,
    OutputDiscoveryState,
    ResourceDiagnostic,
    ResourceNotFoundError,
)


async def list_job_result_resources(
    context: JobResultContext,
    results: JobResults,
    process: ProcessDescription | None,
    *,
    output_name: str | None = None,
    parent_id: str | None = None,
    kind: str | None = None,
) -> JobResultResourceListing:
    """Resolve outputs, select a metadata view, and assess its reader candidates.

    Both client modes call this pipeline after successful job-result retrieval.
    Every original value is eligible for configured discovery, and all outputs
    share one metadata loader/budget. Filtering follows resolver composition;
    capability checks use transformed targets without reading their data.
    """
    assert context.config is not None
    mapping = results.root or {}
    if output_name is not None:
        if output_name not in mapping:
            raise ResourceNotFoundError("Requested job output was not found")
        mapping = {output_name: mapping[output_name]}
    registry = context.config.get_job_result_resolver_registry()
    resources: list[JobResultResource] = []
    contexts: dict[str, JobResultContext] = {}
    states: dict[str, OutputDiscoveryState] = {}
    diagnostics: list[ResourceDiagnostic] = []
    base_uri = (
        f"{context.service_url.rstrip('/')}/jobs/{quote(context.job_id or '', safe='')}/results"
        if context.service_url
        else None
    )
    limit_diagnostic = ResourceDiagnostic(
        code="resource-limit",
        message="Job resource limit reached; discovery is incomplete",
    )
    for name, value in mapping.items():
        await asyncio.sleep(0)
        if len(resources) >= context.limits.max_resources:
            states[name] = OutputDiscoveryState(
                discovery_state="unresolved", diagnostics=(limit_diagnostic,)
            )
            if limit_diagnostic not in diagnostics:
                diagnostics.append(limit_diagnostic)
            continue
        ctx = replace(
            context,
            output_name=name,
            value=value,
            output_description=(process.outputs or {}).get(name) if process else None,
            process_description=process,
            base_uri=_inline_base_uri(value, base_uri),
        )
        contexts[name] = ctx
        listing = await resolve_job_result(ctx, *registry.resolver_types)
        state = listing.discovery_state
        notices = list(listing.diagnostics)
        remaining = context.limits.max_resources - len(resources)
        if len(listing) > remaining:
            state = "partial"
            notices.append(limit_diagnostic)
        resources.extend(listing.resources[:remaining])
        states[name] = OutputDiscoveryState(
            discovery_state=state, diagnostics=tuple(notices)
        )
        diagnostics.extend(notices)
    if parent_id is not None:
        parent = next((r for r in resources if r.id == parent_id), None)
        if parent is None:
            raise ResourceNotFoundError(
                "Requested parent is absent from the loaded resources"
            )
        states = {parent.output_name: states[parent.output_name]}
        diagnostics = list(states[parent.output_name].diagnostics)
        members = [r for r in resources if r.parent_id == parent_id]
        document = parent.metadata.get("stac", {})
        navigation = document.get("links", ()) if isinstance(document, Mapping) else ()
        if not isinstance(navigation, (list, tuple)):
            navigation = ()
        if parent.kind in {"stac-catalog", "stac-collection"} and any(
            isinstance(link, Mapping) and link.get("rel") in {"item", "items", "child"}
            for link in navigation
        ):
            diagnostic = ResourceDiagnostic(
                code="deferred-traversal",
                message="Remote container member traversal is not implemented yet",
            )
            diagnostics.append(diagnostic)
            states[parent.output_name] = OutputDiscoveryState(
                discovery_state="partial", diagnostics=tuple(diagnostics)
            )
    elif kind is None:
        members = [
            r for r in resources if r.kind not in {"stac-item", "stac-item-collection"}
        ]
    else:
        members = resources
    if kind is not None:
        selected = [r for r in members if r.kind == kind]
        for name in states:
            owned = [r for r in resources if r.output_name == name]
            if (
                kind
                in {
                    "stac-item",
                    "stac-item-collection",
                    "stac-collection",
                    "stac-catalog",
                    "asset",
                }
                and owned
                and not any(r.kind.startswith("stac-") or r.kind == kind for r in owned)
                and states[name].discovery_state == "complete"
            ):
                diagnostic = ResourceDiagnostic(
                    code="unsupported-kind",
                    severity="error",
                    message=f"Output does not describe resources of kind {kind!r}",
                )
                diagnostics.append(diagnostic)
                states[name] = OutputDiscoveryState(
                    discovery_state="error",
                    diagnostics=(*states[name].diagnostics, diagnostic),
                )
        members = selected
    opener_types = context.config.get_job_result_opener_registry().opener_types
    assessed = []
    for resource in members:
        await asyncio.sleep(0)
        assessed.append(
            await assess_job_result(
                resource, *opener_types, context=contexts[resource.output_name]
            )
        )
    return JobResultResourceListing(
        resources=tuple(assessed),
        discovery_state=_aggregate_state(states),
        diagnostics=tuple(diagnostics),
        output_states=states,
    )


def _validate_listing_arguments(
    job_id: str,
    output_name: str | None,
    parent_id: str | None,
    kind: str | None,
    data_type: type | None,
    limits: DiscoveryLimits | None,
    refresh: bool,
) -> None:
    for value, required in (
        (job_id, True),
        (output_name, False),
        (parent_id, False),
        (kind, False),
    ):
        if value is None and not required:
            continue
        if not isinstance(value, str) or not value:
            raise TypeError("Job and resource selectors must be nonempty strings")
    if data_type is not None and not isinstance(data_type, type):
        raise TypeError("data_type must be a Python type")
    if limits is not None and not isinstance(limits, DiscoveryLimits):
        raise TypeError("limits must be DiscoveryLimits")
    if not isinstance(refresh, bool):
        raise TypeError("refresh must be a boolean")


def _inline_base_uri(value: Any, fallback: str | None) -> str | None:
    value = json_value(value)
    if isinstance(value, dict) and "mediaType" in value and "value" in value:
        value = value["value"]
    if not isinstance(value, dict):
        return fallback
    links = value.get("links", [])
    if not isinstance(links, list):
        return fallback
    selves = set()
    for link in links:
        if (
            not isinstance(link, dict)
            or link.get("rel") != "self"
            or not isinstance(link.get("href"), str)
        ):
            continue
        try:
            if urlsplit(link["href"]).scheme:
                selves.add(link["href"])
        except ValueError:
            continue
    return selves.pop() if len(selves) == 1 else fallback


def _aggregate_state(states: dict[str, OutputDiscoveryState]) -> DiscoveryState:
    values = {s.discovery_state for s in states.values()}
    if not values or values == {"complete"}:
        return "complete"
    if len(values) == 1:
        return next(iter(values))
    return "partial"
