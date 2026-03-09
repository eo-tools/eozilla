#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import geopandas as gpd
import pandas as pd
import pytest
import xarray as xr

from cuiman.api.opener import JobResultOpenError
from cuiman.api.opener.impl import (
    GeopandasDataFrameOpener,
    PandasDataFrameOpener,
    XarrayDatasetOpener,
)
from gavicore.models import Link

from .test_base import create_ctx


class GeopandasDataFrameOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(GeopandasDataFrameOpener.is_usable())
        with patch.dict("sys.modules", {"geopandas": None}):
            self.assertFalse(GeopandasDataFrameOpener.is_usable())

    @patch("geopandas.read_parquet")
    async def test_open_job_result(self, mock_read_parquet):
        fake_gdf = gpd.GeoDataFrame({"a": [1, 2, 3]})
        mock_read_parquet.return_value = fake_gdf

        opener = GeopandasDataFrameOpener()
        ctx = create_ctx(
            Link(
                href="s3://regions/region-data.geoparquet",
                type="application/geoparquet",
            )
        )
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_gdf)
        mock_read_parquet.assert_called_once_with(
            "s3://regions/region-data.geoparquet",
        )

    @patch("geopandas.read_feather")
    async def test_open_job_result_from_filename_ext(self, mock_read_parquet):
        fake_gdf = gpd.GeoDataFrame({"a": [1, 2, 3]})
        mock_read_parquet.return_value = fake_gdf

        opener = GeopandasDataFrameOpener()
        ctx = create_ctx(
            Link(
                href="s3://regions/region-data.feather",
                type="application/octet-stream",
            )
        )
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_gdf)
        mock_read_parquet.assert_called_once_with(
            "s3://regions/region-data.feather",
        )

    @patch("geopandas.read_file")
    async def test_open_job_result_from_default(self, mock_read_parquet):
        fake_gdf = gpd.GeoDataFrame({"a": [1, 2, 3]})
        mock_read_parquet.return_value = fake_gdf

        opener = GeopandasDataFrameOpener()
        ctx = create_ctx(
            Link(
                href="s3://regions/region-data.geojson",
                type="application/json",
            )
        )
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_gdf)
        mock_read_parquet.assert_called_once_with(
            "s3://regions/region-data.geojson",
        )


class PandasDataFrameOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(PandasDataFrameOpener.is_usable())
        with patch.dict("sys.modules", {"pandas": None}):
            self.assertFalse(PandasDataFrameOpener.is_usable())

    @patch("pandas.read_parquet")
    async def test_open_job_result_for_media_type(self, mock_read_parquet):
        fake_df = pd.DataFrame({"a": [1, 2, 3]})
        mock_read_parquet.return_value = fake_df

        opener = PandasDataFrameOpener()
        ctx = create_ctx(
            Link(
                href="s3://regions/region-data.parquet",
                type="application/parquet",
            )
        )
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_df)
        mock_read_parquet.assert_called_once_with(
            "s3://regions/region-data.parquet",
        )

    @patch("pandas.read_csv")
    async def test_open_job_result_for_filename_ext(self, mock_read_parquet):
        fake_df = pd.DataFrame({"a": [1, 2, 3]})
        mock_read_parquet.return_value = fake_df

        opener = PandasDataFrameOpener()
        ctx = create_ctx(
            Link(
                href="s3://regions/region-data.csv",
                type="text/plain",
            )
        )
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_df)
        mock_read_parquet.assert_called_once_with(
            "s3://regions/region-data.csv",
        )

    async def test_open_job_result_fails(self):
        opener = PandasDataFrameOpener()
        ctx = create_ctx(
            Link(
                href="s3://regions/region-data.tar.gz",
                type="application/octet-stream",
            )
        )
        with pytest.raises(
            JobResultOpenError, match="No appropriate pandas read function found"
        ):
            await opener.open_job_result(ctx)


class XarrayDatasetOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(XarrayDatasetOpener.is_usable())
        with patch.dict("sys.modules", {"geopandas": None}):
            self.assertFalse(GeopandasDataFrameOpener.is_usable())

    @patch("xarray.open_dataset")
    async def test_open_job_result(self, mock_open_dataset):
        fake_ds = xr.Dataset({"a": ("x", [1, 2, 3])})
        mock_open_dataset.return_value = fake_ds

        opener = XarrayDatasetOpener()
        ctx = create_ctx(
            Link(
                href="https://example.com/cube.zarr?off=0x64ea",
                type="application/x-zarr",
            )
        )
        ctx.options = {"chunks": {"x": 2}, "decode_times": False}
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_ds)
        mock_open_dataset.assert_called_once_with(
            "https://example.com/cube.zarr?off=0x64ea",
            chunks={"x": 2},
            decode_times=False,
        )
