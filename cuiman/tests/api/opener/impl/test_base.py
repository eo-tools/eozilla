#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.opener import JobResultOpenContext
from cuiman.api.opener.impl.base import (
    BasePathOpener,
    get_path_or_url,
    get_filename_ext,
)
from gavicore.models import (
    JobResults,
    InlineOrRefValue,
    Link,
    InlineValue,
)


class BasePathOpenerOpener(BasePathOpener):
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

    async def open_path_or_url(
        self,
        path_or_url: str,
        filename_ext: str,
        media_type: str | None,
        ctx: JobResultOpenContext,
    ) -> Any:
        self.path_or_url = path_or_url
        self.filename_ext = filename_ext
        self.media_type = media_type
        return 137


def create_ctx(
    return_value: InlineValue | Link,
):
    return JobResultOpenContext(
        config=ClientConfig(api_url="https://example.com/"),
        job_id="job_10",
        job_results=JobResults(**{"return_value": InlineOrRefValue(root=return_value)}),
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

int_value = InlineValue(root=45763)


@pytest.mark.asyncio
async def test_base_opener_is_usable():
    assert TestPathOrUrlOpener.is_usable() is True


@pytest.mark.asyncio
async def test_base_opener_accept_job_result():
    await assert_accept_job_result(
        zarr_link,
        accepts_filename_ext=True,
        accepts_media_type=True,
        accepts_data_type=True,
        expected_result=True,
    )
    await assert_accept_job_result(
        int_value,
        accepts_filename_ext=True,
        accepts_media_type=True,
        accepts_data_type=True,
        expected_result=False,
    )
    await assert_accept_job_result(
        zarr_link,
        accepts_filename_ext=False,
        accepts_media_type=True,
        accepts_data_type=True,
        expected_result=False,
    )
    await assert_accept_job_result(
        zarr_link,
        accepts_filename_ext=True,
        accepts_media_type=False,
        accepts_data_type=True,
        expected_result=False,
    )
    await assert_accept_job_result(
        zarr_link,
        accepts_filename_ext=True,
        accepts_media_type=True,
        accepts_data_type=False,
        expected_result=False,
    )


async def assert_accept_job_result(
    value: Link | InlineValue,
    accepts_filename_ext: bool,
    accepts_media_type: bool,
    accepts_data_type: bool,
    expected_result: bool,
):
    opener = TestPathOrUrlOpener()
    ctx = create_ctx(value)
    opener.accepts_filename_ext = accepts_filename_ext
    opener.accepts_media_type = accepts_media_type
    opener.accepts_data_type = accepts_data_type
    assert (await opener.accept_job_result(ctx)) is expected_result


@pytest.mark.asyncio
async def test_base_opener_open_job_result():
    opener = TestPathOrUrlOpener()
    ctx = create_ctx(nc_link)
    assert (await opener.open_job_result(ctx)) == 137
    assert opener.path_or_url == "https://example.com/cube.nc?off=0x64ea"
    assert opener.filename_ext == ".nc"
    assert opener.media_type == "application/x-netcdf"


def test_get_path_or_url():
    ctx = create_ctx(nc_link)
    assert get_path_or_url(ctx) == "https://example.com/cube.nc?off=0x64ea"

    ctx = create_ctx(int_value)
    assert get_path_or_url(ctx) is None

    ctx = create_ctx(InlineValue(root="regions.gpckg"))
    assert get_path_or_url(ctx) == "regions.gpckg"

    ctx = create_ctx(InlineValue(root={"path": "./dataset.zarr"}))
    assert get_path_or_url(ctx) == "./dataset.zarr"


def test_get_filename_ext():
    assert get_filename_ext("https://example.com/cube.nc?off=0x64ea") == ".nc"
    assert get_filename_ext("dataset.gpckg") == ".gpckg"
    assert get_filename_ext("./data.set.zarr") == ".zarr"
