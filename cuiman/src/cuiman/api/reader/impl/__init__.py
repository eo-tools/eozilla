#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from ._stac.composition import compose_stac_reader
from .base import (
    OptionalModuleReader,
    PathReader,
)
from .readers import (
    GeopandasDataFrameReader,
    ImageReader,
    PandasDataFrameReader,
    StacJobResultReader,
    XarrayDatasetReader,
)

__all__ = [
    "PathReader",
    "OptionalModuleReader",
    "GeopandasDataFrameReader",
    "ImageReader",
    "PandasDataFrameReader",
    "StacJobResultReader",
    "XarrayDatasetReader",
    "compose_stac_reader",
]
