#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Any

from .context import JobResultOpenContext
from .opener import JobResultOpener
import importlib

_PATH_LIKE_KEYS = {"path", "href", "url"}
_PATH_LIKE_TYPES = (str, Path)


class XarrayDatasetOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        try:
            xr = importlib.import_module("xarray")
        except ImportError:
            return False
        return ctx.data_type is xr.Dataset

    async def open(self, ctx: JobResultOpenContext) -> Any:
        import xarray as xr

        path_or_url = _get_path_or_url(ctx)
        return xr.open_dataset(path_or_url, **ctx.options)


def _get_path_or_url(ctx: JobResultOpenContext) -> Any:
    path_or_url: Any = None
    if ctx.output_link:
        path_or_url = ctx.output_link.href
    output_value = ctx.output_value.model_dump()
    if isinstance(output_value, _PATH_LIKE_TYPES):
        path_or_url = output_value
    elif isinstance(output_value, dict):
        path_or_url = any(
            v
            for k, v in output_value.items()
            if k in _PATH_LIKE_KEYS and isinstance(v, _PATH_LIKE_TYPES)
        )
    if not path_or_url:
        raise ValueError("Cannot determine path or URL from job result")
    return path_or_url
