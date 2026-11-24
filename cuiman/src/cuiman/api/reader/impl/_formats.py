# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Format matching shared by dataset readers and Asset option preparation."""

from urllib.parse import urlsplit


def is_zarr(media_type: str | None, location: str) -> bool:
    """Identify Zarr from media type, using the suffix only if it is absent."""
    if media_type:
        return media_type.split(";", 1)[0].strip().lower() in {
            "application/zarr",
            "application/x-zarr",
            "application/vnd+zarr",
            "application/vnd.zarr",
        }
    return urlsplit(location).path.rstrip("/").lower().endswith(".zarr")
