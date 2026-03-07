#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from cuiman.api.opener import JobResultOpener
from .base import OptionalModuleOpener


class GeopandasDataFrameOpener(OptionalModuleOpener):
    module_names = ("geopandas",)

    def create_implementing_opener(self) -> JobResultOpener:
        from ._gpd import GeopandasDataFrameOpenerImpl

        return GeopandasDataFrameOpenerImpl()


class PandasDataFrameOpener(OptionalModuleOpener):
    module_names = ("pandas",)

    def create_implementing_opener(self) -> JobResultOpener:
        from ._pd import PandasDataFrameOpenerImpl

        return PandasDataFrameOpenerImpl()


class XarrayDatasetOpener(OptionalModuleOpener):
    module_names = ("xarray",)

    def create_implementing_opener(self) -> JobResultOpener:
        from ._xr import XarrayDatasetOpenerImpl

        return XarrayDatasetOpenerImpl()
