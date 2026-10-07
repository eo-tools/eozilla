#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Resolver contract, dispatch, and shared description helpers."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError

from gavicore.models import Link, QualifiedValue

from ..resources import (
    DiscoveryState,
    JobResultResource,
    JobResultResourceListing,
    OutputDiscoveryState,
    ResourceDiagnostic,
)
from .context import DiscoveryError, ResolutionContext


class JobResultResolver(ABC):
    """Discover resource descriptions without reading data payloads.

    One selected resolver owns an output's semantic interpretation and may
    produce zero, one, or many flat resources. The result includes containers
    needed for later inspection; user-facing view filtering follows resolution
    and transformation. Acceptance must not transform or enumerate resources.
    """

    @abstractmethod
    async def accept(self, ctx: ResolutionContext) -> bool:
        """Inspect any original value/schema, sharing bounded metadata loading."""

    @abstractmethod
    async def resolve(self, ctx: ResolutionContext) -> JobResultResourceListing:
        """Return resources, ownership, states, and diagnostics for one output."""


async def resolve_job_result(
    ctx: ResolutionContext, *resolver_types: type[JobResultResolver]
) -> JobResultResourceListing:
    """Select one resolver in priority order, with an unconditional value fallback.

    Original values are eligible before Link normalization or STAC detection.
    A failed selected resolver leaves the original output inspectable with a
    diagnostic; cancellation propagates. No results from accepting siblings are
    combined. Configuration supplies specialized classes before the built-ins.
    """
    from .impl import ValueResolver

    for resolver_type in resolver_types:
        assert_resolver_type_valid(resolver_type)
        try:
            resolver = resolver_type()
            if await resolver.accept(ctx):
                return await resolver.resolve(ctx)
        except Exception as exc:
            fallback = await ValueResolver().resolve(ctx)
            diagnostic = discovery_diagnostic(
                exc, "resolver-failure", resolver_type.__name__
            )
            state: DiscoveryState = (
                "partial"
                if isinstance(exc, DiscoveryError) and exc.partial
                else "error"
            )
            resource = fallback[0].with_updates(
                discovery_state=state, diagnostics=(diagnostic,)
            )
            return result_listing(
                ctx, [resource], state=state, diagnostics=(diagnostic,)
            )
    return await ValueResolver().resolve(ctx)


def output_link(value: Any) -> Link | None:
    """Normalize a typed or raw OGC Link, without probing its target."""
    if isinstance(value, Link):
        return value
    if isinstance(value, dict) and isinstance(value.get("href"), str):
        try:
            return Link.model_validate(value)
        except ValidationError:
            return None
    return None


def output_media_type(value: Any) -> str | None:
    """Return advertised media metadata, retaining all media type parameters."""
    if isinstance(value, Link):
        return value.type
    if isinstance(value, QualifiedValue):
        return value.mediaType
    if isinstance(value, dict):
        media_type = value.get("type") if output_link(value) else value.get("mediaType")
        return media_type if isinstance(media_type, str) else None
    return None


def json_value(value: Any) -> Any:
    """Convert OGC model instances to their JSON representation without mutation."""
    return (
        value.model_dump(mode="json", by_alias=True)
        if isinstance(value, BaseModel)
        else value
    )


def output_provenance(ctx: ResolutionContext) -> dict[str, Any]:
    """Describe the source output separately from effective resource access."""
    return {
        "job_id": ctx.job_id,
        "service_url": ctx.service_url,
        "output_name": ctx.output_name,
        "output_value": json_value(ctx.value),
        "output_description": json_value(ctx.output_description),
        "process_id": ctx.process_description.id if ctx.process_description else None,
    }


def result_listing(
    ctx: ResolutionContext,
    resources: list[JobResultResource] | tuple[JobResultResource, ...],
    *,
    state: DiscoveryState = "complete",
    diagnostics: tuple[ResourceDiagnostic, ...] = (),
) -> JobResultResourceListing:
    """Build one flat listing with state even when its output produces no rows."""
    return JobResultResourceListing(
        resources=tuple(resources),
        discovery_state=state,
        diagnostics=diagnostics,
        output_states={
            ctx.output_name: OutputDiscoveryState(
                discovery_state=state, diagnostics=diagnostics
            )
        },
    )


def discovery_diagnostic(
    error: Exception, code: str, subject: str
) -> ResourceDiagnostic:
    """Report a failure without exposing arbitrary runtime exception messages."""
    return ResourceDiagnostic(
        code=error.code if isinstance(error, DiscoveryError) else code,
        message=error.message
        if isinstance(error, DiscoveryError)
        else f"{subject} failed ({type(error).__name__})",
        severity="error",
    )


def assert_resolver_type_valid(resolver_type: type[JobResultResolver]) -> None:
    """Reject extension entries that are not JobResultResolver subclasses."""
    if not isinstance(resolver_type, type) or not issubclass(
        resolver_type, JobResultResolver
    ):
        raise TypeError("Expected a JobResultResolver subclass")
