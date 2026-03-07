#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import geopandas as gpd

from cuiman.api.opener.impl._gpd import GeopandasDataFrameOpener
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from gavicore.models import Link
from .test_base import create_ctx


class GeopandasDataFrameOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(GeopandasDataFrameOpener.is_usable())

    def test_accept_data_type(self):
        opener = GeopandasDataFrameOpener()
        self.assertFalse(opener.accept_data_type(int))
        self.assertTrue(opener.accept_data_type(gpd.GeoDataFrame))

        with patch.dict("sys.modules", {"geopandas": None}):
            self.assertFalse(opener.accept_data_type(gpd.GeoDataFrame))

    def test_accept_filename_ext(self):
        opener = GeopandasDataFrameOpener()
        self.assertTrue(opener.accept_filename_ext(".json"))
        self.assertTrue(opener.accept_filename_ext(".parquet"))
        self.assertTrue(opener.accept_filename_ext(".geoparquet"))

    def test_accept_media_type(self):
        opener = GeopandasDataFrameOpener()
        self.assertTrue(opener.accept_media_type("text/json"))
        self.assertTrue(opener.accept_media_type("application/parquet"))
        self.assertTrue(opener.accept_media_type("application/geoparquet"))

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
