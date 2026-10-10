"""Native STAC parsing using PySTAC's standard I/O and lazy navigation."""

import asyncio
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

import pystac

from cuiman.api.opener.context import JobResultOpenContext
from cuiman.api.opener.errors import StacJobResultOpenError
from cuiman.api.opener.impl._paths import _local_path
from cuiman.api.opener.opener import JobResultOpener
from .locations import _absolute, _resolve_href
from .support import (
    candidate_stac,
    selected_document,
    strong_stac,
    structural_stac,
)


class StacJobResultOpenerImpl(JobResultOpener):
    """Parse only selected metadata, preserving native lazy navigation."""

    def __init__(self) -> None:
        self._stac_io: pystac.StacIO | None = None

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return candidate_stac(ctx)

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        required = strong_stac(ctx)
        reading = False
        try:
            factory = type(ctx.config).stac_io_factory
            self._stac_io = factory(ctx.config) if factory else pystac.StacIO.default()
            io = self._stac_io
            document = selected_document(ctx)
            base = ctx.document_href
            if ctx.location and not structural_stac(document):
                reading = True
                location = _resolve_href(ctx.location, base)
                source = (
                    str(_local_path(location))
                    if urlsplit(location).scheme == "file"
                    else location
                )
                # PySTAC reads synchronously. Keep network/file I/O off the loop.
                document = await asyncio.to_thread(io.read_json, source)
                reading = False
                base = _self_href(document, location) or location
            elif isinstance(document, dict):
                base = _self_href(document, base) or base
            required = required or structural_stac(document)
            if not required:
                raise StacJobResultOpenError(
                    "Document has no STAC structural evidence", required=False
                )
            result = _parse(document, base, io)
            if ctx.data_type is not None and not isinstance(result, ctx.data_type):
                raise StacJobResultOpenError(
                    "STAC document does not match the requested native type"
                )
            return result
        except StacJobResultOpenError as error:
            raise StacJobResultOpenError(
                str(error), required=required or reading
            ) from None
        except Exception as error:
            raise StacJobResultOpenError(
                f"STAC metadata parsing failed ({type(error).__name__})",
                required=required or reading,
            ) from None


def _parse(
    document: Any,
    base: str | None,
    io: pystac.StacIO,
    root: pystac.Catalog | None = None,
) -> Any:
    if not isinstance(document, dict):
        raise StacJobResultOpenError("STAC metadata must be an object")
    document = deepcopy(document)
    if document.get("type") == "FeatureCollection":
        features = document.get("features")
        if not isinstance(features, list) or any(
            not isinstance(item, dict)
            or item.get("type") != "Feature"
            or "stac_version" not in item
            for item in features
        ):
            raise StacJobResultOpenError("ItemCollection must contain STAC Items")
        _normalize_links(document, base)
        items = [_parse(item, base, io, root) for item in features]
        # Avoid ItemCollection's default cloning, which would drop per-object I/O.
        return pystac.ItemCollection(
            items,
            extra_fields={
                key: value
                for key, value in document.items()
                if key not in {"type", "features"}
            },
            clone_items=False,
        )
    if (
        document.get("type") not in {"Feature", "Catalog", "Collection"}
        or "stac_version" not in document
    ):
        raise StacJobResultOpenError("Document is not supported STAC metadata")
    _normalize_links(document, base)
    for asset in document.get("assets", {}).values():
        asset["href"] = _resolve_href(asset["href"], base)
    # PySTAC's native parser assigns concrete Asset owners without any reads.
    result = io.stac_object_from_dict(
        document, href=base, root=root, preserve_dict=False
    )
    return result


def _normalize_links(document: dict[str, Any], base: str | None) -> None:
    for link in document.get("links", []):
        link["href"] = _resolve_href(link["href"], base)


def _self_href(
    document: dict[str, Any], containing_base: str | None = None
) -> str | None:
    hrefs = {
        link.get("href")
        for link in document.get("links", [])
        if isinstance(link, dict) and link.get("rel") == "self"
    }
    if not hrefs:
        return None
    if len(hrefs) != 1:
        raise StacJobResultOpenError("Inline STAC self location is ambiguous")
    href = next(iter(hrefs))
    if not isinstance(href, str) or not _absolute(href):
        if containing_base is not None:
            return None
        raise StacJobResultOpenError("Inline STAC self location must be absolute")
    return _resolve_href(href, None)
