#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import xarray as xr

from cuiman.api.reader import JobResultReadContext

from ._formats import is_zarr
from .base import PathReader


class XarrayDatasetReaderImpl(PathReader):
    reader_id = "xarray"
    option_policy = "xarray"

    def accept_data_type(self, data_type: type) -> bool:
        # TODO: Support conversions to other representations, such as Zarr to pandas.
        return data_type is xr.Dataset

    def accept_media_type(self, media_type: str) -> bool:
        return (
            is_zarr(media_type, "")
            or media_type.startswith("image/")
            or media_type
            in {
                "application/netcdf",
                "application/x-netcdf",
                "application/hdf",
                "application/x-hdf",
                "application/x-hdf5",
                "application/x-grib",
                "application/grib",
                "application/cog",
                "application/x-cog",
                "application/octet-stream",
            }
        )

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return True

    async def read_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultReadContext,
    ) -> Any:
        options = dict(ctx.options)
        if "engine" not in options and is_zarr(media_type, path_like):
            options["engine"] = "zarr"
        # Return the backend's lazy dataset without loading or closing it.
        return xr.open_dataset(path_like, **options)
