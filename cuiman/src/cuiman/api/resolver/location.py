#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Location-aware reference resolution without filesystem or storage I/O."""

import ntpath
import posixpath
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from .context import DiscoveryError


def resolve_location(
    location: str, base: str | None = None, *, folder: bool = False
) -> str:
    """Resolve a reference against a document or explicitly declared folder.

    Absolute entries retain their location. Relative entries require an absolute
    base. Filesystem paths, file URIs, HTTP and hierarchical object-store URIs
    are supported. A folder base is a directory even without a trailing slash.
    No file existence checks, directory scans, or credential inheritance occur.
    """
    if not location:
        raise DiscoveryError("invalid-location", "A non-empty location is required")
    uri_base = (
        base is not None and not _absolute_path(base) and bool(urlsplit(base).scheme)
    )
    rooted_reference = uri_base and not folder and location.startswith("/")
    if (_absolute_path(location) and not rooted_reference) or urlsplit(location).scheme:
        return location
    if not base:
        raise DiscoveryError("missing-base", "Relative reference has no absolute base")
    if _absolute_path(base):
        windows = bool(ntpath.splitdrive(base)[0]) or base.startswith("\\\\")
        paths = ntpath if windows else posixpath
        return paths.normpath(
            paths.join(base if folder else paths.dirname(base), location)
        )
    parts = urlsplit(base)
    if parts.scheme not in {
        "http",
        "https",
        "file",
        "s3",
        "gs",
        "az",
        "abfs",
        "abfss",
        "memory",
    }:
        raise DiscoveryError("ambiguous-base", "Unsupported or relative reference base")
    if parts.scheme == "file":
        location = location.replace("\\", "/")
    # urljoin does not treat object-store schemes as hierarchical. Resolve with
    # HTTP semantics, then restore the base scheme; retain query/fragment rules.
    base_path = parts.path.rstrip("/") + "/" if folder else parts.path
    surrogate = urlunsplit(
        ("https", parts.netloc or "_local_", base_path, parts.query, parts.fragment)
    )
    joined = urlsplit(urljoin(surrogate, quote(location, safe="/%:@?=&+#[]!$'()*;,~")))
    return urlunsplit(
        (
            parts.scheme,
            "" if joined.netloc == "_local_" else joined.netloc,
            joined.path,
            joined.query,
            joined.fragment,
        )
    )


def _absolute_path(location: str) -> bool:
    return (
        location.startswith("/")
        or location.startswith("\\\\")
        or bool(ntpath.splitdrive(location)[0])
    )
