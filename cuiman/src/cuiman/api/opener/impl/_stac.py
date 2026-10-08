"""Native STAC parsing and per-object bounded navigation policy."""

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import pystac
from pystac.utils import HREF

from ..context import JobResultOpenContext
from ..errors import StacJobResultOpenError
from ..metadata import StacMetadataIO
from ..opener import JobResultOpener
from ._stac_support import (
    candidate_stac,
    selected_document,
    strong_stac,
    structural_stac,
)


class StacJobResultOpenerImpl(JobResultOpener):
    """Parse only selected metadata, preserving native lazy navigation."""

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        return candidate_stac(ctx)

    async def open_job_result(self, ctx: JobResultOpenContext) -> Any:
        required = strong_stac(ctx)
        reading = False
        try:
            if ctx._stac_metadata_io is None:
                ctx._stac_metadata_io = ctx.config.create_stac_metadata_io()
            reader = ctx._stac_metadata_io
            document = selected_document(ctx)
            base = ctx.document_href
            if ctx.location and not structural_stac(document):
                reading = True
                location = _resolve_href(ctx.location, base)
                text, base = await reader.async_read_text_with_href(location)
                reading = False
                document = json.loads(text)
            elif isinstance(document, dict):
                base = _self_href(document, base) or base
            required = required or structural_stac(document)
            if not required:
                raise StacJobResultOpenError(
                    "Document has no STAC structural evidence", required=False
                )
            result = _parse(document, base, reader)
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
                required=required,
            ) from None


class _BoundedStacIO(pystac.StacIO):
    def __init__(self, reader: StacMetadataIO):
        super().__init__()
        self._reader = reader

    def read_text(self, source: HREF, *args: Any, **kwargs: Any) -> str:
        return self._reader.new_operation().read_text_with_href(os.fspath(source))[0]

    def write_text(self, dest: HREF, txt: str, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Cuiman STAC metadata policy is read-only")

    def read_stac_object(
        self,
        source: HREF,
        root: pystac.Catalog | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> pystac.STACObject:
        reader = self._reader.new_operation()
        text, base = reader.read_text_with_href(os.fspath(source))
        try:
            result = _parse(json.loads(text), base, reader, root)
            if not isinstance(result, pystac.STACObject):
                raise StacJobResultOpenError("Navigation requires a STAC object")
            return result
        except StacJobResultOpenError:
            raise
        except Exception as error:
            raise StacJobResultOpenError(
                f"STAC metadata parsing failed ({type(error).__name__})"
            ) from None


def _parse(
    document: Any,
    base: str | None,
    reader: StacMetadataIO,
    root: pystac.Catalog | None = None,
) -> Any:
    if not isinstance(document, dict):
        raise StacJobResultOpenError("STAC metadata must be an object")
    document = deepcopy(document)
    io = _BoundedStacIO(reader)
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
        items = [_parse(item, base, reader, root) for item in features]
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


def _absolute(href: str) -> bool:
    parsed = urlsplit(href)
    return Path(href).is_absolute() or bool(
        parsed.scheme
        and (parsed.netloc or parsed.scheme == "file" and parsed.path.startswith("/"))
    )


def _resolve_href(href: str, base: str | None) -> str:
    if not isinstance(href, str) or not href:
        raise StacJobResultOpenError("STAC location must be a non-empty string")
    if Path(href).is_absolute() and (
        base is None
        or urlsplit(base).scheme == "file"
        or "\\" in href
        or (os.name == "nt" and len(urlsplit(href).scheme) == 1)
    ):
        return Path(href).as_uri()
    if urlsplit(href).scheme:
        return href
    if base is None:
        raise StacJobResultOpenError(
            "Relative STAC location has no containing document base"
        )
    base = _resolve_href(base, None)
    parsed = urlsplit(base)
    if not parsed.scheme or not (parsed.netloc or parsed.scheme == "file"):
        raise StacJobResultOpenError(
            "STAC containing document base is not hierarchical"
        )
    # urljoin only supports its built-in schemes; storage URIs are hierarchical too.
    joined = urlsplit(
        urljoin(
            urlunsplit(
                ("https", parsed.netloc, parsed.path, parsed.query, parsed.fragment)
            ),
            href,
        )
    )
    return urlunsplit(
        (parsed.scheme, joined.netloc, joined.path, joined.query, joined.fragment)
    )
