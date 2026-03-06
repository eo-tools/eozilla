#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from functools import cached_property
from pathlib import Path
from typing import Any

from param import Callable

from .context import JobResultOpenContext
from .opener import JobResultOpener

_PATH_LIKE_KEYS = ("href", "url", "path")
_PATH_LIKE_TYPES = (str, Path)


class XarrayDatasetOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        path_or_url = get_path_or_url(ctx)
        if not path_or_url:
            return False
        try:
            import xarray
        except ImportError:
            return False
        if ctx.data_type not in (None, xarray.Dataset):
            return False
        return True

    async def open(self, ctx: JobResultOpenContext) -> Any:
        import xarray

        # from accept() we know
        # - path_or_url is given
        # - xarray is available
        path_or_url = get_path_or_url(ctx)
        assert path_or_url  # from accept() we know we have path_or_url
        return xarray.open_dataset(str(path_or_url), **ctx.options)


class PandasDataFrameOpener(JobResultOpener):
    async def accept(self, ctx: JobResultOpenContext) -> bool:
        path_or_url = get_path_or_url(ctx)
        if not path_or_url:
            return False
        try:
            import pandas
        except ImportError:
            return False
        if ctx.data_type not in (None, pandas.DataFrame):
            return False
        return True

    async def open(self, ctx: JobResultOpenContext) -> Any:
        import pandas

        # from accept() we know
        # - path_or_url is given
        # - xarray is available
        path_or_url = get_path_or_url(ctx)

    @cached_property
    def mime_type_readers(self) -> dict[str, Callable]:
        try:
            import pandas as pd
        except ImportError:
            return {}
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

    @cached_property
    def file_ext_readers(self) -> dict[str, Callable]:
        try:
            import pandas as pd
        except ImportError:
            return {}
        return {
        ".csv":
            return pd.read_csv(path, **options)
        ".parquet":
            return pd.read_parquet(path, **options)
        ".xls":
    ".xlsx":
            return pd.read_excel(path, **options)
       ".h5": ".hdf": ".hdf5":
            return pd.read_hdf(path, **options)
        if ext == ".json":
            return pd.read_json(path, **options)
        }

def open_dataframe(path: str | Path, media_type: str | None = None, **options):
    path = Path(path)

    if media_type:
        if media_type == "text/csv":
            return pd.read_csv(path, **options)
        if media_type == "application/parquet":
            return pd.read_parquet(path, **options)
        if media_type in {
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }:
            return pd.read_excel(path, **options)
        if media_type in {"application/x-hdf", "application/x-hdf5"}:
            return pd.read_hdf(path, **options)

    ext = path.suffix.lower()

    if ext == ".csv":
        return pd.read_csv(path, **options)
    if ext == ".parquet":
        return pd.read_parquet(path, **options)
    if ext in {".xls", ".xlsx"}:
        return pd.read_excel(path, **options)
    if ext in {".h5", ".hdf", ".hdf5"}:
        return pd.read_hdf(path, **options)
    if ext == ".json":
        return pd.read_json(path, **options)

    raise ValueError(f"Unsupported format: media_type={media_type}, extension={ext}")


def open_geodataframe(path: str | Path, media_type: str | None = None, **options):
    path = Path(path)

    if media_type:
        if media_type in {"application/geo+json", "application/json"}:
            return gpd.read_file(path, **options)
        if media_type == "application/geoparquet":
            return gpd.read_parquet(path, **options)
        if media_type == "application/vnd.apache.parquet":
            return gpd.read_parquet(path, **options)
        if media_type == "application/x-feather":
            return gpd.read_feather(path, **options)

    ext = path.suffix.lower()

    if ext in {".geojson", ".json", ".gpkg", ".shp", ".gml", ".kml"}:
        return gpd.read_file(path, **options)
    if ext in {".parquet"}:
        return gpd.read_parquet(path, **options)
    if ext in {".feather"}:
        return gpd.read_feather(path, **options)

    raise ValueError(f"Unsupported format: media_type={media_type}, extension={ext}")


def get_path_or_url(ctx: JobResultOpenContext) -> Any:
    if ctx.output_link:
        return ctx.output_link.href
    output_value = ctx.output_value.model_dump()
    if isinstance(output_value, _PATH_LIKE_TYPES):
        return output_value
    elif isinstance(output_value, dict):
        for k in _PATH_LIKE_KEYS:
            v = output_value.get(k)
            if v is not None and isinstance(v, _PATH_LIKE_TYPES):
                return v
    return None
