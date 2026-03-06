#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import pandas as pd

from cuiman.api.opener.impl.pd import PandasDataFrameOpener
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from gavicore.models import Link
from .test_base import create_ctx


class PandasDataFrameOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(PandasDataFrameOpener.is_usable())

    def test_accept_data_type(self):
        opener = PandasDataFrameOpener()
        self.assertFalse(opener.accept_data_type(int))
        self.assertTrue(opener.accept_data_type(pd.DataFrame))

        with patch.dict("sys.modules", {"pandas": None}):
            self.assertFalse(opener.accept_data_type(pd.DataFrame))

    def test_accept_filename_ext(self):
        opener = PandasDataFrameOpener()
        self.assertFalse(opener.accept_filename_ext(".zarr"))
        self.assertFalse(opener.accept_filename_ext(".tif"))
        self.assertTrue(opener.accept_filename_ext(".json"))
        self.assertTrue(opener.accept_filename_ext(".parquet"))

    def test_accept_media_type(self):
        opener = PandasDataFrameOpener()
        self.assertFalse(opener.accept_media_type("application/x-zarr"))
        self.assertFalse(opener.accept_media_type("application/x-cog"))
        self.assertTrue(opener.accept_media_type("text/json"))
        self.assertTrue(opener.accept_media_type("application/parquet"))

    @patch("pandas.read_parquet")
    async def test_open_job_result(self, mock_read_parquet):
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
