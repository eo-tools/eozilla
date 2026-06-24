#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
import pytest
import xarray as xr
from PIL import Image

from cuiman.api.opener import JobResultOpenContext, JobResultOpenError
from cuiman.api.opener.impl import (
    GeopandasDataFrameOpener,
    ImageOpener,
    PandasDataFrameOpener,
    XarrayDatasetOpener,
)
from gavicore.models import JobResults, Link

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


class ImageOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(ImageOpener.is_usable())
        with patch.dict("sys.modules", {"PIL": None}):
            self.assertFalse(ImageOpener.is_usable())

    @patch("PIL.Image.open")
    async def test_open_job_result_local(self, mock_image_open):
        fake_image = Image.new("RGB", (10, 10))
        mock_image_open.return_value = fake_image

        opener = ImageOpener()
        ctx = create_ctx(Link(href="/path/to/image.png", type="image/png"))
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_image)
        mock_image_open.assert_called_once_with("/path/to/image.png")

    async def test_open_job_result_s3(self):
        fake_image = Image.new("RGB", (10, 10))
        fake_opened = MagicMock()
        fake_opened.copy.return_value = fake_image

        mock_file = MagicMock()
        mock_fs = MagicMock()
        mock_fs.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_fs.open.return_value.__exit__ = MagicMock(return_value=False)

        mock_s3fs_module = MagicMock()
        mock_s3fs_module.S3FileSystem.return_value = mock_fs

        with patch.dict("sys.modules", {"s3fs": mock_s3fs_module}):
            with patch("PIL.Image.open", return_value=fake_opened):
                opener = ImageOpener()
                ctx = create_ctx(
                    Link(href="s3://my-bucket/images/photo.png", type="image/png")
                )
                ctx.options = {"storage_options": {"anon": True}}
                result = await opener.open_job_result(ctx)

        self.assertIs(result, fake_image)
        mock_s3fs_module.S3FileSystem.assert_called_once_with(anon=True)
        mock_fs.open.assert_called_once_with("s3://my-bucket/images/photo.png", "rb")
        fake_opened.copy.assert_called_once()

    async def test_accept_job_result(self):
        opener = ImageOpener()

        ctx = JobResultOpenContext(
            config=create_ctx(Link(href="/image.png", type="image/png")).config,
            job_id="test",
            job_results=JobResults(
                **{"return_value": Link(href="/image.png", type="image/png")}
            ),
            data_type=Image.Image,
        )
        self.assertTrue(await opener.accept_job_result(ctx))

        ctx_wrong_type = JobResultOpenContext(
            config=create_ctx(Link(href="/image.png", type="image/png")).config,
            job_id="test",
            job_results=JobResults(
                **{"return_value": Link(href="/image.png", type="image/png")}
            ),
            data_type=int,
        )
        self.assertFalse(await opener.accept_job_result(ctx_wrong_type))

    async def test_accept_job_result_s3_without_s3fs(self):
        opener = ImageOpener()
        ctx = create_ctx(Link(href="s3://my-bucket/images/photo.png", type="image/png"))
        ctx.data_type = Image.Image
        with patch.dict("sys.modules", {"s3fs": None}):
            self.assertFalse(await opener.accept_job_result(ctx))
