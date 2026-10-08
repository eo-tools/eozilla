#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable

import geopandas as gpd

from ...context import JobResultContext
from ...resources import JobResultResource
from .base import PathOpener


class GeopandasDataFrameOpenerImpl(PathOpener):
    """GeoPandas adapter selecting a reader from this resource's format or suffix."""

    def accept_data_type(self, data_type: type) -> bool:
        return data_type is gpd.GeoDataFrame

    def accept_media_type(self, media_type: str) -> bool:
        return True

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return True

    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        resource: JobResultResource,
        context: JobResultContext,
    ) -> Any:
        """Read the selected geospatial table using scoped storage settings."""
        # See if we need a special geopandas read function
        read_x = (
            self.media_type_readers.get(media_type.partition(";")[0].strip().lower())
            if media_type
            else None
        )
        if read_x is None:
            read_x = self.filename_ext_readers.get(filename_ext)
        if read_x is not None:
            return read_x(path_like, **await context.reader_options(resource))

        # Use geopandas's generic read function
        return gpd.read_file(path_like, **await context.reader_options(resource))

    @property
    def media_type_readers(self) -> dict[str, Callable]:
        return {
            "application/parquet": gpd.read_parquet,
            "application/geoparquet": gpd.read_parquet,
            "application/vnd.apache.parquet": gpd.read_parquet,
            "application/x-feather": gpd.read_feather,
        }

    @property
    def filename_ext_readers(self) -> dict[str, Callable]:
        return {
            ".parquet": gpd.read_parquet,
            ".geoparquet": gpd.read_parquet,
            ".feather": gpd.read_feather,
        }
