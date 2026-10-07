#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Resolver-owned transformation chains and declared folder descendants."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from gavicore.models import Link

from ..resources import (
    JobResultResource,
    JobResultResourceListing,
    ResourceCapabilities,
    make_resource_id,
)
from .context import DiscoveryError, ResolutionContext
from .location import resolve_location
from .resolver import JobResultResolver, discovery_diagnostic, result_listing


class ResourceTransformer(ABC):
    """Enrich, rewrite, or expand one resolved resource without mutating it.

    Return the unchanged resource for a non-match. Expansion normally includes
    the source ancestor. Later stages receive this stage's results; the same
    stage is never reapplied recursively to its own descendants.
    """

    @abstractmethod
    async def transform(
        self, resource: JobResultResource, ctx: ResolutionContext
    ) -> tuple[JobResultResource, ...]:
        """Return replacements using only metadata and shared discovery services."""


class ComposedJobResultResolver(JobResultResolver):
    """Delegate recognition/discovery and apply an owned, ordered transformer chain.

    Registered subclasses supply their base and transformers in a no-argument
    constructor. An optional acceptance predicate scopes project-specific
    behavior before base acceptance. Transformation runs only after selection.
    Failures preserve the preceding resource and successful siblings. Capability
    snapshots on changed descriptions are reset for later client assessment.
    """

    def __init__(
        self,
        base: JobResultResolver,
        transformers: Sequence[ResourceTransformer],
        *,
        accepts: Callable[[ResolutionContext], bool] | None = None,
    ):
        self._base = base
        self._transformers = tuple(transformers)
        self._accepts = accepts

    async def accept(self, ctx: ResolutionContext) -> bool:
        """Check project scope and base recognition without running transformers."""
        return (
            self._accepts is None or self._accepts(ctx)
        ) and await self._base.accept(ctx)

    async def resolve(self, ctx: ResolutionContext) -> JobResultResourceListing:
        """Transform the selected base's flat view using the same operation context."""
        listing = await self._base.resolve(ctx)
        resources = listing.resources
        diagnostics = list(listing.diagnostics)
        for transformer in self._transformers:
            transformed: list[JobResultResource] = []
            seen: set[str] = set()
            # Reserve remaining source identities so a malformed expansion cannot
            # displace a successful sibling before that sibling is transformed.
            source_ids = {resource.id for resource in resources}
            for resource in resources:
                await asyncio.sleep(0)
                try:
                    replacements = await transformer.transform(resource, ctx)
                    if not isinstance(replacements, tuple) or not all(
                        isinstance(r, JobResultResource) for r in replacements
                    ):
                        raise TypeError("Transformers must return a tuple of resources")
                    ids = [r.id for r in replacements]
                    if (
                        len(ids) != len(set(ids))
                        or set(ids) & seen
                        or (set(ids) - {resource.id}) & source_ids
                    ):
                        raise ValueError(
                            "Transformation produced duplicate resource identities"
                        )
                    if any(r.output_name != ctx.output_name for r in replacements):
                        raise ValueError("Transformation changed output ownership")
                    remaining = len(source_ids - seen - {resource.id})
                    if (
                        len(transformed) + len(replacements) + remaining
                        > ctx.limits.max_resources
                    ):
                        raise DiscoveryError(
                            "resource-limit",
                            "Transformed resource limit reached",
                            partial=True,
                        )
                    replacements = tuple(
                        _derived(r, resource, transformer) for r in replacements
                    )
                except Exception as exc:
                    diagnostic = discovery_diagnostic(
                        exc, "transformation-failure", type(transformer).__name__
                    )
                    diagnostics.append(diagnostic)
                    replacements = (
                        resource.with_updates(
                            discovery_state="partial",
                            diagnostics=(*resource.diagnostics, diagnostic),
                        ),
                    )
                transformed.extend(replacements)
                seen.update(r.id for r in replacements)
                source_ids.discard(resource.id)
            resources = tuple(transformed)
        partial = len(diagnostics) > len(listing.diagnostics) or any(
            r.discovery_state in {"partial", "error"} for r in resources
        )
        result = result_listing(
            ctx,
            resources,
            state="partial" if partial else listing.discovery_state,
            diagnostics=tuple(diagnostics),
        )
        return result.model_copy(update={"continuation": listing.continuation})


@dataclass(frozen=True)
class ResourceEntry:
    """One developer-supplied descendant; this is not an external config format.

    The extension owns configuration acquisition and declares directory nodes
    explicitly. Locations of children are relative to their parent directory.
    No format or credentials are inferred from an ancestor's description.
    """

    key: str
    """Stable entry identity, independent of its effective access location."""
    location: str
    """Relative path or explicitly supplied absolute access location."""
    kind: str = "asset"
    """Semantic kind; use ``container`` for a declared directory node."""
    title: str | None = None
    """Configured display title; the entry key remains its fallback."""
    description: str | None = None
    """Configured human-readable description."""
    media_type: str | None = None
    """This entry's advertised format, including media type parameters."""
    roles: tuple[str, ...] = ()
    """This entry's advertised roles; absent roles remain unspecified."""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    """Non-secret metadata copied into the derived snapshot."""
    open_hints: Mapping[str, Any] = field(default_factory=dict)
    """Non-secret reader defaults belonging to this entry."""
    access: Mapping[str, Any] = field(default_factory=dict)
    """Explicit non-secret access requirements; ancestor credentials are not 
    inherited."""
    children: tuple["ResourceEntry", ...] = ()
    """Declared immediate descendants of a directory node."""

    def __post_init__(self) -> None:
        if not self.key or not self.location:
            raise ValueError("Resource entries require a key and location")
        if self.children and self.kind != "container":
            raise ValueError("Only declared containers may have children")


class FolderResourceTransformer(ResourceTransformer):
    """Expand matching folder resources from declared metadata without storage I/O.

    Completeness describes the supplied configuration, never an exhaustive or
    verified directory inventory. Selectors depend on the source identity and
    entry keys, so location renewal does not change them. Results are rebuilt
    on every resolution; only source documents are cached by the shared loader.
    """

    def __init__(
        self,
        entries: Sequence[ResourceEntry] | None,
        *,
        matches: Callable[[JobResultResource, ResolutionContext], bool],
        config_id: str | None = None,
        config_revision: str | None = None,
    ):
        self._entries = tuple(entries) if entries is not None else None
        self._matches = matches
        self._config_id = config_id
        self._config_revision = config_revision

    async def transform(
        self, resource: JobResultResource, ctx: ResolutionContext
    ) -> tuple[JobResultResource, ...]:
        """Retain the folder and describe valid configured descendants and failures."""
        if not self._matches(resource, ctx):
            return (resource,)
        if self._entries is None:
            raise DiscoveryError(
                "folder-configuration", "Folder configuration is unavailable"
            )
        if resource.link is None:
            raise DiscoveryError(
                "folder-base", "Configured folder has no access location"
            )
        source_location = resource.link.href
        resources = [resource]
        diagnostics = []

        async def expand(
            entries: tuple[ResourceEntry, ...],
            parent: JobResultResource,
            ancestry: tuple[str, ...],
            depth: int,
        ) -> None:
            keys: set[str] = set()
            for entry in entries:
                await asyncio.sleep(0)
                try:
                    if depth > ctx.limits.max_depth:
                        raise DiscoveryError(
                            "depth-limit",
                            "Declared subtree depth limit reached",
                            partial=True,
                        )
                    if len(resources) >= ctx.limits.max_resources:
                        raise DiscoveryError(
                            "resource-limit",
                            "Declared subtree resource limit reached",
                            partial=True,
                        )
                    if entry.key in keys:
                        raise DiscoveryError(
                            "duplicate-entry",
                            "Declared siblings repeat an entry identity",
                        )
                    keys.add(entry.key)
                    assert parent.link is not None
                    location = resolve_location(
                        entry.location, parent.link.href, folder=True
                    )
                    identity = (*ancestry, entry.key)
                    child = JobResultResource(
                        id=make_resource_id(
                            ctx.output_name, resource.id, "entry", *identity
                        ),
                        output_name=ctx.output_name,
                        parent_id=parent.id,
                        item_id=resource.item_id,
                        path=f"{parent.path}/{quote(entry.key, safe='')}",
                        kind=entry.kind,
                        key=entry.key,
                        link=Link(
                            href=location, type=entry.media_type, title=entry.title
                        ),
                        media_type=entry.media_type,
                        title=entry.title,
                        description=entry.description,
                        roles=entry.roles,
                        metadata=dict(entry.metadata)
                        | {"directory_inventory_complete": False},
                        open_hints=dict(entry.open_hints),
                        access=dict(entry.access),
                        provenance=resource.model_dump(mode="json")["provenance"]
                        | {
                            "source_resource_id": resource.id,
                            "source_location": source_location,
                            "declared_location": entry.location,
                            "declared_base": parent.link.href,
                            "configuration_id": self._config_id,
                            "configuration_revision": self._config_revision,
                        },
                        discovery_state="complete",
                    )
                    resources.append(child)
                    await expand(entry.children, child, identity, depth + 1)
                except Exception as exc:
                    diagnostics.append(
                        discovery_diagnostic(exc, "folder-entry", "Declared entry")
                    )

        await expand(self._entries, resource, (), 1)
        if diagnostics:
            resources[0] = resource.with_updates(
                discovery_state="partial",
                diagnostics=(*resource.diagnostics, *diagnostics),
            )
        return tuple(resources)


def _derived(
    result: JobResultResource,
    source: JobResultResource,
    transformer: ResourceTransformer,
) -> JobResultResource:
    if result == source:
        return source
    provenance = result.model_dump(mode="json")["provenance"]
    history = provenance.get("transformations", [])
    provenance["transformations"] = [
        *history,
        {
            "transformer": f"{type(transformer).__module__}.{type(transformer).__qualname__}",
            "source_resource_id": source.id,
        },
    ]
    return result.with_updates(
        provenance=provenance, capabilities=ResourceCapabilities()
    )
