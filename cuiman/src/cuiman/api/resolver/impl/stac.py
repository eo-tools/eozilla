#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Structural STAC recognition and initial, metadata-only discovery."""

import asyncio
from typing import Any
from urllib.parse import quote, urlsplit

from gavicore.models import Link, QualifiedValue

from ...resources import (
    JobResultResource,
    JobResultResourceListing,
    ResourceDiagnostic,
    make_resource_id,
)
from ..context import DiscoveryError, ResolutionContext
from ..location import resolve_location
from ..resolver import (
    JobResultResolver,
    discovery_diagnostic,
    json_value,
    output_link,
    output_media_type,
    output_provenance,
    result_listing,
)


class StacResolver(JobResultResolver):
    """Recognize STAC structure without full validation or optional dependencies.

    Initial discovery enumerates embedded Items and concrete Assets. Collection
    and Catalog navigation remains unresolved and never triggers a crawl.
    References use the shared loader and containing document URI. Unknown
    fields are preserved. Client traversal and continuation routing build on
    this initial view; this class does not fetch advertised next pages.
    """

    async def accept(self, ctx: ResolutionContext) -> bool:
        """Use schema/inline evidence before a bounded JSON metadata probe."""
        schema, strong = _schema_evidence(ctx)
        if strong:
            return True
        if output_link(ctx.value) is None:
            return (
                _kind(_payload(ctx.value), explicit=schema or ctx.stac_hint) is not None
            )
        media = (output_media_type(ctx.value) or "").partition(";")[0].strip().lower()
        if not (
            schema
            or ctx.stac_hint
            or media in {"application/json", "application/geo+json"}
            or media.endswith("+json")
        ):
            return False
        value, _ = await _document(ctx)
        return _kind(value, explicit=schema or ctx.stac_hint) is not None

    async def resolve(self, ctx: ResolutionContext) -> JobResultResourceListing:
        """Describe loaded STAC containers and Assets, preserving malformed siblings."""
        value, base = await _document(ctx)
        schema, _ = _schema_evidence(ctx)
        kind = _kind(value, explicit=schema or ctx.stac_hint)
        if kind is None:
            raise DiscoveryError(
                "stac-mismatch", "Output does not have the advertised STAC structure"
            )
        resources: list[JobResultResource] = []
        diagnostics: list[ResourceDiagnostic] = []
        truncated = False

        def add(
            document: dict[str, Any],
            owner_kind: str,
            ancestry: tuple[str, ...],
            parent: JobResultResource | None = None,
        ) -> JobResultResource | None:
            if len(resources) >= ctx.limits.max_resources:
                return None
            item_id = document.get("id") if owner_kind == "stac-item" else None
            resource = JobResultResource(
                id=make_resource_id(ctx.output_name, *ancestry),
                output_name=ctx.output_name,
                parent_id=parent.id if parent else None,
                path="/".join(
                    quote(part, safe="") for part in (ctx.output_name, *ancestry)
                ),
                kind=owner_kind,
                key=_text(document, "id"),
                item_id=item_id,
                value=document,
                media_type="application/geo+json"
                if owner_kind in {"stac-item", "stac-item-collection"}
                else "application/json",
                title=_text(document, "title")
                or _text(document.get("properties", {}), "title"),
                description=_text(document, "description"),
                metadata={
                    "stac": document,
                    "document_base": base,
                    "detection": "structural",
                },
                provenance=output_provenance(ctx),
                discovery_state="unresolved"
                if owner_kind in {"stac-collection", "stac-catalog"}
                else "complete",
            )
            resources.append(resource)
            version = document.get("stac_version")
            if version and version not in {"1.0.0", "1.1.0"}:
                diagnostics.append(
                    ResourceDiagnostic(
                        code="stac-version",
                        message="STAC version is outside the recognized core versions",
                    )
                )
            if document.get("stac_extensions"):
                diagnostics.append(
                    ResourceDiagnostic(
                        code="stac-extensions",
                        message="Extension metadata is preserved without extension validation",
                        severity="info",
                    )
                )
            return resource

        ancestry = (kind, value["id"]) if kind != "stac-item-collection" else ()
        root = add(value, kind, ancestry)
        assert root is not None  # Positive resource budget guarantees the root.
        owners: list[tuple[dict[str, Any], JobResultResource]] = []
        if kind in {"stac-item", "stac-collection"}:
            owners.append((value, root))
        if kind == "stac-item-collection":
            seen: set[str] = set()
            for index, item in enumerate(value["features"]):
                await asyncio.sleep(0)
                if index >= ctx.limits.max_items:
                    diagnostics.append(
                        ResourceDiagnostic(
                            code="item-limit", message="Embedded Item limit reached"
                        )
                    )
                    break
                if _kind(item) != "stac-item":
                    diagnostics.append(
                        ResourceDiagnostic(
                            code="invalid-item",
                            message=f"Member {index} is not a recognized STAC Item",
                            severity="error",
                        )
                    )
                    continue
                if item["id"] in seen:
                    diagnostics.append(
                        ResourceDiagnostic(
                            code="duplicate-item",
                            message=f"Member {index} repeats an Item identity",
                            severity="error",
                        )
                    )
                    continue
                seen.add(item["id"])
                owner = add(item, "stac-item", ("item", item["id"]), root)
                if owner is None:
                    truncated = True
                    break
                owners.append((item, owner))
            if any(
                isinstance(link, dict) and link.get("rel") == "next"
                for link in value.get("links", [])
            ):
                diagnostics.append(
                    ResourceDiagnostic(
                        code="next-page",
                        message=(
                            "Further Items are advertised; "
                            "explicit continuation is required"
                        ),
                    )
                )
        for document, owner in owners:
            assets = document.get("assets", {})
            if not isinstance(assets, dict):
                diagnostics.append(
                    ResourceDiagnostic(
                        code="invalid-assets",
                        message="Container Assets are not an object",
                        severity="error",
                    )
                )
                continue
            if (
                owner.parent_id is not None
                and ctx.limits.max_depth < 2
                and document.get("assets")
            ):
                diagnostics.append(
                    ResourceDiagnostic(
                        code="depth-limit", message="Embedded Asset depth limit reached"
                    )
                )
                continue
            for key, asset in assets.items():
                await asyncio.sleep(0)
                if len(resources) >= ctx.limits.max_resources:
                    truncated = True
                    break
                resources.append(_asset(ctx, owner, key, asset, base))
        if truncated:
            diagnostics.append(
                ResourceDiagnostic(
                    code="resource-limit",
                    message="Resource limit reached; the loaded view is incomplete",
                )
            )
        # Container navigation is deferred even when initial embedded discovery
        # is complete. Resource-level failures do not hide successful siblings.
        incomplete = any(
            d.code
            in {
                "item-limit",
                "depth-limit",
                "resource-limit",
                "next-page",
                "duplicate-item",
                "invalid-item",
                "invalid-assets",
            }
            for d in diagnostics
        ) or any(r.diagnostics for r in resources)
        return result_listing(
            ctx,
            resources,
            state="partial" if incomplete else "complete",
            diagnostics=tuple(diagnostics),
        )


def _payload(value: Any) -> Any:
    if isinstance(value, QualifiedValue):
        return value.value
    if isinstance(value, dict) and "mediaType" in value and "value" in value:
        return value["value"]
    return json_value(value)


async def _document(ctx: ResolutionContext) -> tuple[Any, str | None]:
    link = output_link(ctx.value)
    if link is not None:
        if ctx.loader is None:
            raise DiscoveryError(
                "metadata-loader", "Referenced discovery requires a metadata loader"
            )
        document = await ctx.loader.load(resolve_location(link.href, ctx.base_uri))
        return document.value, document.base_uri
    value = _payload(ctx.value)
    base = ctx.base_uri
    if not base and isinstance(value, dict):
        selves: set[str] = set()
        for candidate in value.get("links", []):
            if (
                not isinstance(candidate, dict)
                or candidate.get("rel") != "self"
                or not isinstance(candidate.get("href"), str)
            ):
                continue
            try:
                if urlsplit(candidate["href"]).scheme:
                    selves.add(candidate["href"])
            except ValueError:
                continue
        if len(selves) == 1:
            base = selves.pop()
    return value, base


def _kind(value: Any, *, explicit: bool = False) -> str | None:
    if not isinstance(value, dict):
        return None
    if value.get("type") == "FeatureCollection" and isinstance(
        value.get("features"), list
    ):
        if any(_kind(item) == "stac-item" for item in value["features"]) or (
            not value["features"] and explicit
        ):
            return "stac-item-collection"
        return None
    if (
        not isinstance(value.get("stac_version"), str)
        or not isinstance(value.get("id"), str)
        or not isinstance(value.get("links"), list)
    ):
        return None
    if (
        value.get("type") == "Feature"
        and "geometry" in value
        and isinstance(value.get("properties"), dict)
        and isinstance(value.get("assets"), dict)
    ):
        return "stac-item"
    if isinstance(value.get("description"), str):
        if value.get("type") == "Catalog":
            return "stac-catalog"
        if (
            value.get("type") == "Collection"
            and isinstance(value.get("extent"), dict)
            and isinstance(value.get("license"), str)
        ):
            return "stac-collection"
    return None


def _schema_evidence(ctx: ResolutionContext) -> tuple[bool, bool]:
    schema = (
        json_value(ctx.output_description.schema_) if ctx.output_description else None
    )
    if not isinstance(schema, dict):
        return False, False
    visited: set[str] = set()
    inspected = 0

    def inspect(node: Any, depth: int = 0) -> tuple[bool, bool]:
        nonlocal inspected
        inspected += 1
        if (
            not isinstance(node, dict)
            or depth >= ctx.limits.max_depth
            or inspected > ctx.limits.max_resources
        ):
            return False, False
        reference = node.get("$ref")
        if isinstance(reference, str):
            uri = urlsplit(reference)
            if uri.hostname in {
                "schemas.stacspec.org",
                "stacspec.org",
            } and uri.path.endswith(
                ("/item.json", "/collection.json", "/catalog.json")
            ):
                return True, True
            if reference.startswith("#/") and reference not in visited:
                visited.add(reference)
                target: Any = schema
                for part in reference[2:].split("/"):
                    target = (
                        target.get(part.replace("~1", "/").replace("~0", "~"))
                        if isinstance(target, dict)
                        else None
                    )
                reference_evidence = inspect(target, depth + 1)
                visited.remove(reference)
                return reference_evidence
        for keyword in ("oneOf", "anyOf", "allOf"):
            branches = node.get(keyword)
            if isinstance(branches, list) and branches:
                evidence = [
                    inspect(branch, depth + 1)
                    for branch in branches[: ctx.limits.max_resources]
                ]
                if len(branches) > ctx.limits.max_resources:
                    evidence.append((False, False))
                candidate = any(e[0] for e in evidence)
                strong = (
                    any(e[1] for e in evidence)
                    if keyword == "allOf"
                    else all(e[1] for e in evidence)
                )
                if candidate:
                    return True, strong
        properties = node.get("properties", {})
        if isinstance(properties, dict):
            feature_type = properties.get("type", {})
            features = properties.get("features", {})
            if (
                isinstance(feature_type, dict)
                and (
                    feature_type.get("const") == "FeatureCollection"
                    or feature_type.get("enum") == ["FeatureCollection"]
                )
                and isinstance(features, dict)
            ):
                return inspect(features.get("items"), depth + 1)
        return False, False

    return inspect(schema)


def _text(value: Any, key: str) -> str | None:
    text = value.get(key) if isinstance(value, dict) else None
    return text if isinstance(text, str) else None


def _asset(
    ctx: ResolutionContext,
    owner: JobResultResource,
    key: str,
    asset: Any,
    base: str | None,
) -> JobResultResource:
    diagnostics: tuple[ResourceDiagnostic, ...] = ()
    link = None
    try:
        if not isinstance(asset, dict) or not isinstance(asset.get("href"), str):
            raise DiscoveryError("invalid-asset", "Asset has no valid href")
        link = Link(
            href=resolve_location(asset["href"], base),
            type=_text(asset, "type"),
            title=_text(asset, "title"),
        )
    except Exception as exc:
        diagnostics = (discovery_diagnostic(exc, "asset-location", "Asset location"),)
    roles = asset.get("roles", []) if isinstance(asset, dict) else []
    return JobResultResource(
        id=make_resource_id(ctx.output_name, owner.id, "asset", key),
        output_name=ctx.output_name,
        parent_id=owner.id,
        path=f"{owner.path}/{quote(key, safe='')}",
        item_id=owner.item_id,
        kind="asset",
        key=key,
        link=link,
        media_type=_text(asset, "type"),
        title=_text(asset, "title"),
        description=_text(asset, "description"),
        roles=tuple(role for role in roles if isinstance(role, str))
        if isinstance(roles, list)
        else (),
        metadata={"stac_asset": asset, "document_base": base},
        provenance=output_provenance(ctx)
        | {
            "source_resource_id": owner.id,
            "source_container": owner.model_dump(mode="json")["value"],
        },
        discovery_state="error" if diagnostics else "complete",
        diagnostics=diagnostics,
    )
