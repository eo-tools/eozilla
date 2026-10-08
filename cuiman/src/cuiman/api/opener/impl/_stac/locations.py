# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Location normalization shared by STAC metadata and exact Asset targets."""

import os
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from ...errors import StacJobResultOpenError


def _absolute(href: str) -> bool:
    parsed = urlsplit(href)
    return Path(href).is_absolute() or bool(
        parsed.scheme
        and (
            parsed.netloc
            or parsed.scheme == "file"
            and (parsed.path.startswith("/") or Path(parsed.path).is_absolute())
        )
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
