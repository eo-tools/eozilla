"""STAC recognition without optional imports or metadata access."""

from typing import Any
from urllib.parse import urlsplit

from cuiman.api.assets import as_stac_asset
from cuiman.api.opener.context import JobResultOpenContext
from cuiman.api.opener.errors import StacJobResultOpenError


def selected_document(ctx: JobResultOpenContext) -> Any:
    qualified = ctx.output_qualified_value
    return qualified.value if qualified is not None else ctx.value


def requested_stac(ctx: JobResultOpenContext) -> bool:
    datatype = ctx.data_type
    return (
        isinstance(datatype, type)
        and datatype.__module__.startswith("pystac")
        and datatype.__name__ in {"Item", "ItemCollection", "Collection", "Catalog"}
    )


def structural_stac(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if "stac_version" in value:
        return True
    features = value.get("features")
    return (
        value.get("type") == "FeatureCollection"
        and isinstance(features, list)
        and any(isinstance(item, dict) and "stac_version" in item for item in features)
    )


def strong_stac(ctx: JobResultOpenContext) -> bool:
    if requested_stac(ctx) or structural_stac(selected_document(ctx)):
        return True
    description = ctx.output_description
    if description is not None and _schema_hint(
        description.schema_.model_dump(by_alias=True, exclude_none=True)
    ):
        return True
    return "stac" in (ctx.output_media_type or "").lower()


def _schema_hint(value: Any) -> bool:
    if isinstance(value, dict):
        reference = value.get("$ref", "")
        if isinstance(reference, str) and "stac" in reference.lower():
            return True
        if "stac_version" in value.get("properties", {}):
            return True
        return any(_schema_hint(child) for child in value.values())
    return isinstance(value, list) and any(_schema_hint(child) for child in value)


def candidate_stac(ctx: JobResultOpenContext) -> bool:
    if as_stac_asset(ctx.value) is not None:
        return False
    if ctx.data_type is not None and not requested_stac(ctx):
        return False
    if strong_stac(ctx):
        return True
    if not ctx.location:
        return False
    media_type = (ctx.output_media_type or "").split(";", 1)[0].strip().lower()
    return media_type in {"application/json", "application/geo+json"} or (
        not media_type
        and urlsplit(ctx.location).path.lower().endswith((".json", ".geojson"))
    )


def unavailable_error(ctx: JobResultOpenContext) -> StacJobResultOpenError | None:
    """Explain a missing optional dependency only for required STAC metadata."""
    if candidate_stac(ctx) and strong_stac(ctx):
        return StacJobResultOpenError(
            "STAC opening requires the optional cuiman[stac] dependency"
        )
    return None
