#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pandas as pd

# noinspection PyProtectedMember
from cuiman.api.reader.impl._pd import PandasDataFrameReaderImpl


class PandasDataFrameReaderTest(TestCase):
    def test_accept_data_type(self):
        reader = PandasDataFrameReaderImpl()
        self.assertFalse(reader.accept_data_type(int))
        self.assertTrue(reader.accept_data_type(pd.DataFrame))

    def test_accept_filename_ext(self):
        reader = PandasDataFrameReaderImpl()
        self.assertFalse(reader.accept_filename_ext(".zarr"))
        self.assertFalse(reader.accept_filename_ext(".tif"))
        self.assertTrue(reader.accept_filename_ext(".json"))
        self.assertTrue(reader.accept_filename_ext(".parquet"))

    def test_accept_media_type(self):
        reader = PandasDataFrameReaderImpl()
        self.assertFalse(reader.accept_media_type("application/x-zarr"))
        self.assertFalse(reader.accept_media_type("application/x-cog"))
        self.assertTrue(reader.accept_media_type("text/json"))
        self.assertTrue(reader.accept_media_type("application/parquet"))
