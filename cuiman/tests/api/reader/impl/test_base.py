#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest.async_case import IsolatedAsyncioTestCase

import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.reader import JobResultReadContext, JobResultReader
from cuiman.api.reader.impl.base import OptionalModuleReader, PathReader
from gavicore.models.core import (
    InlineValue,
    JobResults,
    Link,
)


class OptionalModuleTestReader(OptionalModuleReader):
    reader_id = "OptionalModuleTestReader"

    required = ()

    def _create_implementing_reader(self) -> JobResultReader:
        return PathTestReader()


class PathTestReader(PathReader):
    reader_id = "PathTestReader"

    def __init__(self):
        # set by tests
        self.accepts_filename_ext: bool = False
        self.accepts_media_type: bool = False
        self.accepts_data_type: bool = False
        # set by read_path_or_url()
        self.path_or_url: str | None = None
        self.filename_ext: str | None = None
        self.media_type: str | None = None

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return self.accepts_filename_ext

    def accept_media_type(self, media_type: str) -> bool:
        return self.accepts_media_type

    def accept_data_type(self, data_type: type) -> bool:
        return self.accepts_data_type

    async def read_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultReadContext,
    ) -> Any:
        self.path_or_url = path_like
        self.filename_ext = filename_ext
        self.media_type = media_type
        return 137


def create_ctx(
    return_value: Link | InlineValue,
):
    return JobResultReadContext(
        config=ClientConfig(api_url="https://example.com/"),
        job_id="job_10",
        job_results=JobResults(**{"return_value": return_value}),
        data_type=int,
    )


zarr_link = Link(
    href="https://example.com/cube.zarr?off=0x64ea",
    type="application/x-zarr",
)

nc_link = Link(
    href="https://example.com/cube.nc?off=0x64ea",
    type="application/x-netcdf",
)

int_value = 45763


class OptionalModuleReaderTest(IsolatedAsyncioTestCase):
    def test_is_usable(self):
        self.assertTrue(OptionalModuleTestReader.is_usable())

    async def test_implementing_reader(self):
        reader = OptionalModuleTestReader()
        self.assertIsInstance(reader.implementing_reader, PathTestReader)
        self.assertIs(reader.implementing_reader, reader.implementing_reader)

    @pytest.mark.asyncio
    async def test_accept_job_result(self):
        reader = OptionalModuleTestReader()
        ctx = create_ctx(nc_link)
        self.assertEqual(False, await reader.accept_job_result(ctx))
        impl_reader: PathTestReader = reader.implementing_reader
        impl_reader.accepts_data_type = True
        impl_reader.accepts_media_type = True
        impl_reader.accepts_filename_ext = True
        self.assertEqual(True, await reader.accept_job_result(ctx))

    @pytest.mark.asyncio
    async def test_read_job_result(self):
        reader = OptionalModuleTestReader()
        ctx = create_ctx(nc_link)
        self.assertEqual(137, await reader.read_job_result(ctx))
        impl_reader: PathTestReader = reader.implementing_reader
        self.assertEqual(
            "https://example.com/cube.nc?off=0x64ea", impl_reader.path_or_url
        )
        self.assertEqual(".nc", impl_reader.filename_ext)
        self.assertEqual("application/x-netcdf", impl_reader.media_type)


class PathReaderTest(IsolatedAsyncioTestCase):
    def test_is_usable(self):
        self.assertTrue(PathTestReader.is_usable())

    async def test_accept_job_result(self):
        await self._assert_accept_job_result(
            zarr_link,
            accepts_filename_ext=True,
            accepts_media_type=True,
            accepts_data_type=True,
            expected_result=True,
        )
        await self._assert_accept_job_result(
            int_value,
            accepts_filename_ext=True,
            accepts_media_type=True,
            accepts_data_type=True,
            expected_result=False,
        )
        await self._assert_accept_job_result(
            zarr_link,
            accepts_filename_ext=False,
            accepts_media_type=True,
            accepts_data_type=True,
            expected_result=False,
        )
        await self._assert_accept_job_result(
            zarr_link,
            accepts_filename_ext=True,
            accepts_media_type=False,
            accepts_data_type=True,
            expected_result=False,
        )
        await self._assert_accept_job_result(
            zarr_link,
            accepts_filename_ext=True,
            accepts_media_type=True,
            accepts_data_type=False,
            expected_result=False,
        )

    async def _assert_accept_job_result(
        self,
        value: Link | InlineValue,
        accepts_filename_ext: bool,
        accepts_media_type: bool,
        accepts_data_type: bool,
        expected_result: bool,
    ):
        reader = PathTestReader()
        ctx = create_ctx(value)
        reader.accepts_filename_ext = accepts_filename_ext
        reader.accepts_media_type = accepts_media_type
        reader.accepts_data_type = accepts_data_type
        self.assertIs(await reader.accept_job_result(ctx), expected_result)

    @pytest.mark.asyncio
    async def test_read_job_result(self):
        reader = PathTestReader()
        ctx = create_ctx(nc_link)
        self.assertEqual(137, await reader.read_job_result(ctx))
        self.assertEqual("https://example.com/cube.nc?off=0x64ea", reader.path_or_url)
        self.assertEqual(".nc", reader.filename_ext)
        self.assertEqual("application/x-netcdf", reader.media_type)

    def test_get_path_or_url(self):
        ctx = create_ctx(nc_link)
        self.assertEqual(
            "https://example.com/cube.nc?off=0x64ea", PathReader.get_path_like(ctx)
        )

        ctx = create_ctx(int_value)
        self.assertIsNone(PathReader.get_path_like(ctx))

        ctx = create_ctx("regions.gpckg")
        self.assertEqual("regions.gpckg", PathReader.get_path_like(ctx))

        ctx = create_ctx({"path": "./dataset.zarr"})
        self.assertEqual("./dataset.zarr", PathReader.get_path_like(ctx))

    async def test_open_selected_location_without_job(self):
        ctx = JobResultReadContext(
            config=ClientConfig(api_url="https://example.com/"),
            value=nc_link,
            location="https://other.example.com/selected.nc?token=example",
        )
        reader = PathTestReader()
        self.assertEqual(137, await reader.read_job_result(ctx))
        self.assertEqual(ctx.location, reader.path_or_url)
        self.assertEqual(".nc", reader.filename_ext)
        self.assertEqual("application/x-netcdf", reader.media_type)
        self.assertEqual("https://example.com/cube.nc?off=0x64ea", nc_link.href)
        self.assertIsNone(ctx.job_results)

    def test_get_filename_ext(self):
        self.assertEqual(
            ".nc", PathReader.get_filename_ext("https://example.com/cube.nc?off=0x64ea")
        )
        self.assertEqual(".gpckg", PathReader.get_filename_ext("dataset.gpckg"))
        self.assertEqual(".zarr", PathReader.get_filename_ext("./data.set.zarr"))
