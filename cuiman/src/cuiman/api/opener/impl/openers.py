#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from ...context import JobResultContext
from ...resources import JobResultResource
from ..opener import JobResultOpener
from .base import OptionalModuleOpener


class GeopandasDataFrameOpener(OptionalModuleOpener):
    """Open geospatial tables through the optional GeoPandas adapter."""

    id = "geopandas"
    hint_types = {
        "columns": list,
        "bbox": list,
        "layer": str,
        "encoding": str,
        "storage_options": dict,
    }
    mergeable_options = frozenset({"storage_options"})
    required = ("geopandas",)

    def _create_implementing_opener(self) -> JobResultOpener:
        from ._gpd import GeopandasDataFrameOpenerImpl

        return GeopandasDataFrameOpenerImpl()


class PandasDataFrameOpener(OptionalModuleOpener):
    """Open tables through the optional pandas adapter."""

    id = "pandas"
    hint_types = {
        "sep": str,
        "encoding": str,
        "header": (int, type(None)),
        "index_col": (int, str, list, type(None)),
        "columns": list,
        "storage_options": dict,
    }
    mergeable_options = frozenset({"storage_options"})
    required = ("pandas",)

    def _create_implementing_opener(self) -> JobResultOpener:
        from ._pd import PandasDataFrameOpenerImpl

        return PandasDataFrameOpenerImpl()


class XarrayDatasetOpener(OptionalModuleOpener):
    """Open datasets through xarray, deriving Zarr defaults from selected metadata."""

    id = "xarray"
    hint_types = {
        "engine": str,
        "chunks": (str, dict, int, type(None)),
        "decode_times": bool,
        "decode_cf": bool,
        "mask_and_scale": bool,
        "drop_variables": (str, list),
        "backend_kwargs": dict,
        "storage_options": dict,
    }
    mergeable_options = frozenset({"backend_kwargs", "storage_options"})
    storage_in_backend = True
    required = ("xarray",)

    def default_options(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> dict[str, Any]:
        """Translate this resource's Zarr format and consolidated metadata."""
        media_type = (
            (context.media_type_for(resource) or "").partition(";")[0].strip().lower()
        )
        options: dict[str, Any] = {}
        if media_type in {"application/zarr", "application/x-zarr"}:
            options["engine"] = "zarr"
            consolidated = resource.metadata.get("consolidated")
            if isinstance(consolidated, bool):
                options["backend_kwargs"] = {"consolidated": consolidated}
        return options

    def _create_implementing_opener(self) -> JobResultOpener:
        from ._xr import XarrayDatasetOpenerImpl

        return XarrayDatasetOpenerImpl()


class ImageOpener(OptionalModuleOpener):
    """Open images through Pillow, with optional scoped S3 access."""

    id = "image"
    hint_types = {"storage_options": dict}
    mergeable_options = frozenset({"storage_options"})
    required = ("PIL",)

    def _create_implementing_opener(self) -> JobResultOpener:
        from PIL import Image

        from ._image import ImageOpenerImpl

        Image.init()
        return ImageOpenerImpl()
