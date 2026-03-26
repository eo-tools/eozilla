#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import xarray as xr

# noinspection PyProtectedMember
from cuiman.api.opener.impl._xr import XarrayDatasetOpenerImpl


class XarrayDatasetOpenerTest(TestCase):
    def test_accept_data_type(self):
        opener = XarrayDatasetOpenerImpl()
        self.assertFalse(opener.accept_data_type(int))
        self.assertTrue(opener.accept_data_type(xr.Dataset))

    def test_accept_filename_ext(self):
        opener = XarrayDatasetOpenerImpl()
        self.assertTrue(opener.accept_filename_ext(".zarr"))
        self.assertTrue(opener.accept_filename_ext(".nc"))
        self.assertTrue(opener.accept_filename_ext(".tif"))

    def test_accept_media_type(self):
        opener = XarrayDatasetOpenerImpl()
        self.assertTrue(opener.accept_media_type("application/x-zarr"))
        self.assertTrue(opener.accept_media_type("application/x-netcdf"))
        self.assertTrue(opener.accept_media_type("application/x-cog"))
