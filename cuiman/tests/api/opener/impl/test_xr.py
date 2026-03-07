#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import xarray as xr

from cuiman.api.opener.impl._xr import XarrayDatasetOpener
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from gavicore.models import Link
from .test_base import create_ctx

zarr_link = Link(
    href="https://example.com/cube.zarr?off=0x64ea",
    type="application/x-zarr",
)


class XarrayDatasetOpenerTest(IsolatedAsyncioTestCase):
    def test_opener_is_usable(self):
        self.assertTrue(XarrayDatasetOpener.is_usable())

    def test_accept_data_type(self):
        opener = XarrayDatasetOpener()
        self.assertFalse(opener.accept_data_type(int))
        self.assertTrue(opener.accept_data_type(xr.Dataset))

        with patch.dict("sys.modules", {"xarray": None}):
            self.assertFalse(opener.accept_data_type(xr.Dataset))

    def test_accept_filename_ext(self):
        opener = XarrayDatasetOpener()
        self.assertTrue(opener.accept_filename_ext(".zarr"))
        self.assertTrue(opener.accept_filename_ext(".nc"))
        self.assertTrue(opener.accept_filename_ext(".tif"))

    def test_accept_media_type(self):
        opener = XarrayDatasetOpener()
        self.assertTrue(opener.accept_media_type("application/x-zarr"))
        self.assertTrue(opener.accept_media_type("application/x-netcdf"))
        self.assertTrue(opener.accept_media_type("application/x-cog"))

    @patch("xarray.open_dataset")
    async def test_open_job_result(self, mock_open_dataset):
        fake_ds = xr.Dataset({"a": ("x", [1, 2, 3])})
        mock_open_dataset.return_value = fake_ds

        opener = XarrayDatasetOpener()
        ctx = create_ctx(zarr_link)
        ctx.options = {"chunks": {"x": 2}, "decode_times": False}
        result = await opener.open_job_result(ctx)
        self.assertIs(result, fake_ds)
        mock_open_dataset.assert_called_once_with(
            "https://example.com/cube.zarr?off=0x64ea",
            chunks={"x": 2},
            decode_times=False,
        )
