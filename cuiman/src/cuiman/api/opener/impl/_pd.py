#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable

import pandas as pd

from cuiman.api.opener import JobResultOpenContext, JobResultOpenError

from .base import BasePathOpener


class PandasDataFrameOpenerImpl(BasePathOpener):
    def accept_data_type(self, data_type: type) -> bool:
        return data_type is pd.DataFrame

    def accept_media_type(self, media_type: str) -> bool:
        return media_type in self.media_type_readers

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return filename_ext in self.filename_ext_readers

    async def open_path_or_url(
        self,
        path_or_url: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        read_x = self.media_type_readers.get(media_type) if media_type else None
        if read_x is None:
            read_x = self.filename_ext_readers.get(filename_ext)
        if read_x is not None:
            return read_x(path_or_url, **ctx.options)
        # Pandas doesn't have a generic read function like xarray or geopandas
        raise JobResultOpenError("No appropriate pandas read function found")

    @property
    def media_type_readers(self) -> dict[str, Callable]:
        return {
            "text/csv": pd.read_csv,
            "text/json": pd.read_json,
            "application/json": pd.read_json,
            "application/parquet": pd.read_parquet,
            "application/x-hdf": pd.read_hdf,
            "application/x-hdf5": pd.read_hdf,
            "application/vnd.ms-excel": pd.read_excel,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": pd.read_excel,
        }

    @property
    def filename_ext_readers(self) -> dict[str, Callable]:
        return {
            ".csv": pd.read_csv,
            ".parquet": pd.read_parquet,
            ".xls": pd.read_excel,
            ".xlsx": pd.read_excel,
            ".h5": pd.read_hdf,
            ".hdf": pd.read_hdf,
            ".hdf5": pd.read_hdf,
            ".json": pd.read_json,
        }
