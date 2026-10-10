# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

from enum import Enum
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from cuiman.api.assets import as_stac_asset
from cuiman.api.opener.errors import JobResultOpenError

if TYPE_CHECKING:
    from cuiman.api.config import ClientConfig
    from cuiman.api.opener.context import JobResultOpenContext


class _Omitted(Enum):
    VALUE = 0


OMITTED = _Omitted.VALUE


def _asset_context(
    config: "ClientConfig",
    target: Any,
    *,
    output_name: Any,
    poll_interval: Any,
    timeout: Any,
    data_type: type | None,
    media_type: str | None,
    options: dict[str, Any],
) -> "JobResultOpenContext":
    from cuiman.api.opener.context import JobResultOpenContext

    asset = as_stac_asset(target)
    if asset is None:
        raise TypeError("job_id must be a job ID string or a pystac.Asset")
    forbidden = [
        name
        for name, value in (
            ("output_name", output_name),
            ("poll_interval", poll_interval),
            ("timeout", timeout),
        )
        if value is not OMITTED
    ]
    if forbidden:
        raise TypeError(
            "Asset opening does not accept job-only arguments: " + ", ".join(forbidden)
        )
    location = _asset_location(asset, asset.href)
    alternate_key = None
    alternates = asset.extra_fields.get("alternate")
    if isinstance(alternates, dict):
        for key, alternate in alternates.items():
            if not isinstance(key, str) or not isinstance(alternate, dict):
                continue
            try:
                candidate = _asset_location(asset, alternate.get("href"))
            except (JobResultOpenError, ValueError):
                # Malformed optional locations must not hide a valid Asset.
                continue
            if _protocol_priority(candidate) < _protocol_priority(location):
                location, alternate_key = candidate, key
    return JobResultOpenContext(
        config=config,
        value=asset,
        location=location,
        asset_alternate=alternate_key,
        data_type=data_type,
        _media_type=media_type if media_type is not None else asset.media_type,
        options=options,
    )


def _protocol_priority(location: str) -> int:
    return {"file": 0, "s3": 1, "http": 2, "https": 2}.get(
        urlsplit(location).scheme.lower(), 3
    )


def _asset_location(asset: Any, href: Any) -> str:
    """Resolve one location against the original Asset's owner without I/O."""
    from .locations import _absolute, _resolve_href

    if not isinstance(href, str) or not href:
        raise JobResultOpenError("Asset href must be a non-empty string")
    if urlsplit(href).scheme and not _absolute(href):
        raise JobResultOpenError("Asset href with a URI scheme must be absolute")
    # A URL's absolute path can still be relative to its owner's HTTP origin.
    base = None
    if not _absolute(href) or href.startswith("/"):
        base = asset.owner.get_self_href() if asset.owner is not None else None
        if base is not None and not _absolute(base):
            raise JobResultOpenError(
                "Relative Asset href requires an absolute owner document base"
            )
        if base is None and not _absolute(href):
            raise JobResultOpenError(
                "Relative Asset href requires an owner with a document base"
            )
    return _resolve_href(href, base)
