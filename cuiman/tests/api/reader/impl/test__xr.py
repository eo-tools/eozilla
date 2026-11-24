#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import xarray as xr

# noinspection PyProtectedMember
from cuiman.api.reader.impl._xr import XarrayDatasetReaderImpl


class XarrayDatasetReaderTest(TestCase):
    def test_accept_data_type(self):
        reader = XarrayDatasetReaderImpl()
        self.assertFalse(reader.accept_data_type(int))
        self.assertTrue(reader.accept_data_type(xr.Dataset))

    def test_accept_filename_ext(self):
        reader = XarrayDatasetReaderImpl()
        self.assertTrue(reader.accept_filename_ext(".zarr"))
        self.assertTrue(reader.accept_filename_ext(".nc"))
        self.assertTrue(reader.accept_filename_ext(".tif"))

    def test_accept_media_type(self):
        reader = XarrayDatasetReaderImpl()
        self.assertTrue(reader.accept_media_type("application/x-zarr"))
        self.assertTrue(reader.accept_media_type("application/x-netcdf"))
        self.assertTrue(reader.accept_media_type("application/x-cog"))
