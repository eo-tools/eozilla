#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable

from cuiman.api.opener import JobResultOpenContext

from .base import PathOrUrlOpener


class GeoPandasGeoDataFrameOpener(PathOrUrlOpener):
    def accept_data_type(self, data_type: type) -> bool:
        try:
            import geopandas as gpd

            return data_type is gpd.GeoDataFrame
        except ImportError:
            return False

    def accept_media_type(self, media_type: str) -> bool:
        return True

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return True

    async def open_path_or_url(
        self,
        path_or_url: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        # See if we need a special geopandas read function
        read_x = self.media_type_readers.get(media_type)
        if read_x is None:
            read_x = self.filename_ext_readers.get(filename_ext)
        if read_x is not None:
            return read_x(path_or_url, **ctx.options)

        # noinspection PyUnresolvedReferences
        import geopandas as gpd

        # Use geopandas's generic read function
        return gpd.read_file(path_or_url, **ctx.options)

    @property
    def media_type_readers(self) -> dict[str, Callable]:
        try:
            import geopandas as gpd
        except ImportError:
            return {}
        return {
            "application/geoparquet": gpd.read_parquet,
            "application/vnd.apache.parquet": gpd.read_parquet,
            "application/x-feather": gpd.read_feather,
        }

    @property
    def filename_ext_readers(self) -> dict[str, Callable]:
        try:
            import geopandas as gpd
        except ImportError:
            return {}
        return {
            ".parquet": gpd.read_parquet,
            ".feather": gpd.read_feather,
        }
