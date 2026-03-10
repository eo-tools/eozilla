#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest.async_case import IsolatedAsyncioTestCase

import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.opener import JobResultOpenContext, JobResultOpener
from cuiman.api.opener.impl.base import OptionalModuleOpener, PathOpener
from gavicore.models import (
    InlineValue,
    JobResults,
    Link,
)


class OptionalModuleTestOpener(OptionalModuleOpener):
    required = ()

    def _create_implementing_opener(self) -> JobResultOpener:
        return PathTestOpener()


class PathTestOpener(PathOpener):
    def __init__(self):
        # set by tests
        self.accepts_filename_ext: bool = False
        self.accepts_media_type: bool = False
        self.accepts_data_type: bool = False
        # set by open_path_or_url()
        self.path_or_url: str | None = None
        self.filename_ext: str | None = None
        self.media_type: str | None = None

    def accept_filename_ext(self, filename_ext: str) -> bool:
        return self.accepts_filename_ext

    def accept_media_type(self, media_type: str) -> bool:
        return self.accepts_media_type

    def accept_data_type(self, data_type: type) -> bool:
        return self.accepts_data_type

    async def open_path_like(
        self,
        path_like: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        self.path_or_url = path_like
        self.filename_ext = filename_ext
        self.media_type = media_type
        return 137


def create_ctx(
    return_value: Link | InlineValue,
):
    return JobResultOpenContext(
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


class OptionalModuleOpenerTest(IsolatedAsyncioTestCase):
    def test_is_usable(self):
        self.assertTrue(OptionalModuleTestOpener.is_usable())

    async def test_implementing_opener(self):
        opener = OptionalModuleTestOpener()
        self.assertIsInstance(opener.implementing_opener, PathTestOpener)
        self.assertIs(opener.implementing_opener, opener.implementing_opener)

    @pytest.mark.asyncio
    async def test_accept_job_result(self):
        opener = OptionalModuleTestOpener()
        ctx = create_ctx(nc_link)
        self.assertEqual(False, await opener.accept_job_result(ctx))
        impl_opener: PathTestOpener = opener.implementing_opener
        impl_opener.accepts_data_type = True
        impl_opener.accepts_media_type = True
        impl_opener.accepts_filename_ext = True
        self.assertEqual(True, await opener.accept_job_result(ctx))

    @pytest.mark.asyncio
    async def test_open_job_result(self):
        opener = OptionalModuleTestOpener()
        ctx = create_ctx(nc_link)
        self.assertEqual(137, await opener.open_job_result(ctx))
        impl_opener: PathTestOpener = opener.implementing_opener
        self.assertEqual(
            "https://example.com/cube.nc?off=0x64ea", impl_opener.path_or_url
        )
        self.assertEqual(".nc", impl_opener.filename_ext)
        self.assertEqual("application/x-netcdf", impl_opener.media_type)


class PathOpenerTest(IsolatedAsyncioTestCase):
    def test_is_usable(self):
        self.assertTrue(PathTestOpener.is_usable())

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
        opener = PathTestOpener()
        ctx = create_ctx(value)
        opener.accepts_filename_ext = accepts_filename_ext
        opener.accepts_media_type = accepts_media_type
        opener.accepts_data_type = accepts_data_type
        self.assertIs(await opener.accept_job_result(ctx), expected_result)

    @pytest.mark.asyncio
    async def test_open_job_result(self):
        opener = PathTestOpener()
        ctx = create_ctx(nc_link)
        self.assertEqual(137, await opener.open_job_result(ctx))
        self.assertEqual("https://example.com/cube.nc?off=0x64ea", opener.path_or_url)
        self.assertEqual(".nc", opener.filename_ext)
        self.assertEqual("application/x-netcdf", opener.media_type)

    def test_get_path_or_url(self):
        ctx = create_ctx(nc_link)
        self.assertEqual(
            "https://example.com/cube.nc?off=0x64ea", PathOpener.get_path_like(ctx)
        )

        ctx = create_ctx(int_value)
        self.assertIsNone(PathOpener.get_path_like(ctx))

        ctx = create_ctx("regions.gpckg")
        self.assertEqual("regions.gpckg", PathOpener.get_path_like(ctx))

        ctx = create_ctx({"path": "./dataset.zarr"})
        self.assertEqual("./dataset.zarr", PathOpener.get_path_like(ctx))

    def test_get_filename_ext(self):
        self.assertEqual(
            ".nc", PathOpener.get_filename_ext("https://example.com/cube.nc?off=0x64ea")
        )
        self.assertEqual(".gpckg", PathOpener.get_filename_ext("dataset.gpckg"))
        self.assertEqual(".zarr", PathOpener.get_filename_ext("./data.set.zarr"))
