#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from cuiman.api.reader.reader import JobResultReader

from .base import OptionalModuleReader


class GeopandasDataFrameReader(OptionalModuleReader):
    """Read tabular geospatial data as a GeoPandas DataFrame."""

    reader_id = "geopandas"
    option_policy = "geopandas"

    required = ("geopandas",)

    def _create_implementing_reader(self) -> JobResultReader:
        from ._gpd import GeopandasDataFrameReaderImpl

        return GeopandasDataFrameReaderImpl()


class PandasDataFrameReader(OptionalModuleReader):
    """Read tabular data as a pandas DataFrame."""

    reader_id = "pandas"
    option_policy = "pandas"

    required = ("pandas",)

    def _create_implementing_reader(self) -> JobResultReader:
        from ._pd import PandasDataFrameReaderImpl

        return PandasDataFrameReaderImpl()


class XarrayDatasetReader(OptionalModuleReader):
    """Read datasets with xarray."""

    reader_id = "xarray"
    option_policy = "xarray"

    required = ("xarray",)

    def _create_implementing_reader(self) -> JobResultReader:
        from ._xr import XarrayDatasetReaderImpl

        return XarrayDatasetReaderImpl()


class ImageReader(OptionalModuleReader):
    """Read images with Pillow."""

    reader_id = "image"
    option_policy = "image"

    required = ("PIL",)

    def _create_implementing_reader(self) -> JobResultReader:
        from PIL import Image

        from ._image import ImageReaderImpl

        Image.init()
        return ImageReaderImpl()


class StacJobResultReader(OptionalModuleReader):
    """Read native STAC metadata when the optional ``cuiman[stac]`` extra is installed."""

    reader_id = "stac"

    required = ("pystac",)

    def _create_implementing_reader(self) -> JobResultReader:
        from ._stac.reader import StacJobResultReaderImpl

        return StacJobResultReaderImpl()
