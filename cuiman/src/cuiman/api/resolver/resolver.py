#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Resolver contract, dispatch, and shared description helpers."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError

from gavicore.models import Link, QualifiedValue

from ..context import JobResultContext
from ..metadata import DiscoveryError
from ..resources import (
    DiscoveryState,
    JobResultResource,
    JobResultResourceListing,
    OutputDiscoveryState,
    ResourceDiagnostic,
)


class JobResultResolver(ABC):
    """Discover resource descriptions without reading data payloads.

    Resolvers make compound outputs, such as STAC documents, selectable as
    individual resources. Openers can then read a selected resource without
    needing to understand the original output's structure.
    One selected resolver owns an output's semantic interpretation and may
    produce zero, one, or many flat resources. The result includes containers
    needed for later inspection; user-facing view filtering follows resolution
    and transformation. Acceptance must not transform or enumerate resources.
    """

    @abstractmethod
    async def accept(self, ctx: JobResultContext) -> bool:
        """Decide whether this resolver should interpret the original output.

        Inspect the value and schema, using the shared loader for bounded
        metadata probes when needed. Dispatch uses this decision to select one
        resolver; resource enumeration belongs to ``resolve()``.
        """

    @abstractmethod
    async def resolve(self, ctx: JobResultContext) -> JobResultResourceListing:
        """Describe selectable resources after dispatch chooses this resolver.

        Include ownership, discovery states, and diagnostics so callers can
        inspect the resulting view and understand any incomplete discovery.
        """


async def resolve_job_result(
    ctx: JobResultContext, *resolver_types: type[JobResultResolver]
) -> JobResultResourceListing:
    """Select one resolver in priority order, with an unconditional value fallback.

    This is the common dispatch path for built-in and application interpretations
    of an output. The fallback ensures unrecognized outputs remain selectable.
    Original values are eligible before Link normalization or STAC detection.
    A failed selected resolver leaves the original output inspectable with a
    diagnostic; cancellation propagates. No results from accepting siblings are
    combined. Configuration supplies specialized classes before the built-ins.
    """
    from .impl import ValueResolver

    ctx.require_output()
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
    """Recognize typed and raw OGC Links consistently across resolvers.

    Return a validated Link, or ``None`` for a value that is not a valid Link,
    without probing the target.
    """
    if isinstance(value, Link):
        return value
    if isinstance(value, dict) and isinstance(value.get("href"), str):
        try:
            return Link.model_validate(value)
        except ValidationError:
            return None
    return None


def output_media_type(value: Any) -> str | None:
    """Read the advertised format from an original OGC output for discovery.

    Handle Links and qualified values, retaining all media type parameters.
    """
    if isinstance(value, Link):
        return value.type
    if isinstance(value, QualifiedValue):
        return value.mediaType
    if isinstance(value, dict):
        media_type = value.get("type") if output_link(value) else value.get("mediaType")
        return media_type if isinstance(media_type, str) else None
    return None


def json_value(value: Any) -> Any:
    """Make OGC model values usable in portable resource metadata.

    Convert model instances to JSON-compatible values with wire field names;
    leave other values unchanged and do not mutate the input.
    """
    return (
        value.model_dump(mode="json", by_alias=True)
        if isinstance(value, BaseModel)
        else value
    )


def output_provenance(ctx: JobResultContext) -> dict[str, Any]:
    """Record where a derived resource came from for later inspection.

    Preserve original output and process facts as provenance, separately from
    the selected resource's effective location, value, and format.
    """
    return {
        "job_id": ctx.job_id,
        "service_url": ctx.service_url,
        "output_name": ctx.output_name,
        "output_value": json_value(ctx.value),
        "output_description": json_value(ctx.output_description),
        "process_id": ctx.process_description.id if ctx.process_description else None,
    }


def result_listing(
    ctx: JobResultContext,
    resources: list[JobResultResource] | tuple[JobResultResource, ...],
    *,
    state: DiscoveryState = "complete",
    diagnostics: tuple[ResourceDiagnostic, ...] = (),
) -> JobResultResourceListing:
    """Package one resolver's resources and progress into a consistent listing.

    Record the output's state even when it produces no resource rows, so an
    empty result does not lose its discovery status or failure explanation.
    """
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
    """Turn an extension failure into an explanation callers can safely display.

    Preserve a ``DiscoveryError`` explanation; for other exceptions report only
    the type, since arbitrary runtime messages may contain credentials.
    """
    return ResourceDiagnostic(
        code=error.code if isinstance(error, DiscoveryError) else code,
        message=error.message
        if isinstance(error, DiscoveryError)
        else f"{subject} failed ({type(error).__name__})",
        severity="error",
    )


def assert_resolver_type_valid(resolver_type: type[JobResultResolver]) -> None:
    """Validate registry and dispatch entries before using a resolver extension.

    Raise ``TypeError`` unless the entry is a ``JobResultResolver`` subclass.
    """
    if not isinstance(resolver_type, type) or not issubclass(
        resolver_type, JobResultResolver
    ):
        raise TypeError("Expected a JobResultResolver subclass")
