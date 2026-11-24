#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import geopandas as gpd

# noinspection PyProtectedMember
from cuiman.api.reader.impl._gpd import GeopandasDataFrameReaderImpl


class GeopandasDataFrameReaderImplTest(TestCase):
    def test_accept_data_type(self):
        reader = GeopandasDataFrameReaderImpl()
        self.assertFalse(reader.accept_data_type(int))
        self.assertTrue(reader.accept_data_type(gpd.GeoDataFrame))

    def test_accept_filename_ext(self):
        reader = GeopandasDataFrameReaderImpl()
        self.assertTrue(reader.accept_filename_ext(".json"))
        self.assertTrue(reader.accept_filename_ext(".parquet"))
        self.assertTrue(reader.accept_filename_ext(".geoparquet"))

    def test_accept_media_type(self):
        reader = GeopandasDataFrameReaderImpl()
        self.assertTrue(reader.accept_media_type("text/json"))
        self.assertTrue(reader.accept_media_type("application/parquet"))
        self.assertTrue(reader.accept_media_type("application/geoparquet"))
