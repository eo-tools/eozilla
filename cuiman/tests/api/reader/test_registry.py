#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest.mock import patch

import pytest
import xarray as xr
from PIL import Image

from cuiman.api.config import ClientConfig
from cuiman.api.reader import (
    JobResultReadContext,
    JobResultReader,
    JobResultReaderRegistry,
)
from cuiman.api.reader.impl import (
    GeopandasDataFrameReader,
    ImageReader,
    PandasDataFrameReader,
    StacJobResultReader,
    XarrayDatasetReader,
)
from cuiman.api.reader.reader import read_job_result
from gavicore.models.core import JobResults, Link


class DummyReader1(JobResultReader):
    reader_id = "DummyReader1"

    async def accept_job_result(self, _ctx: JobResultReadContext) -> bool:
        return False

    async def read_job_result(self, _ctx: JobResultReadContext) -> Any:
        return None


class DummyReader2(DummyReader1):
    reader_id = "DummyReader2"

    pass


class DummyReader3(DummyReader1):
    reader_id = "DummyReader3"

    pass


def test_initially_empty():
    registry = JobResultReaderRegistry()
    assert len(registry.reader_types) == 0


def test_default():
    registry = JobResultReaderRegistry.create_default()
    assert registry.reader_types == (
        StacJobResultReader,
        ImageReader,
        XarrayDatasetReader,
        PandasDataFrameReader,
        GeopandasDataFrameReader,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["png", "jpeg", "jpg"])
@pytest.mark.parametrize("media_type", [None, "image"])
async def test_default_opens_images_before_datasets(extension, media_type):
    href = f"/path/to/image.{extension}"
    if media_type == "image":
        media_type = "image/png" if extension == "png" else "image/jpeg"
    ctx = JobResultReadContext(
        config=ClientConfig(api_url="https://example.com/"),
        job_id="image-job",
        job_results=JobResults(root={"image": Link(href=href, type=media_type)}),
    )
    expected = Image.new("RGB", (2, 2))
    registry = JobResultReaderRegistry.create_default()
    with (
        patch("PIL.Image.open", return_value=expected) as open_image,
        patch("xarray.open_dataset") as open_dataset,
    ):
        result = await read_job_result(ctx, *registry.reader_types)

    assert result is expected
    open_image.assert_called_once_with(href)
    open_dataset.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("data_type,image_usable", [(None, False), (xr.Dataset, True)])
async def test_default_dataset_fallback(data_type, image_usable):
    ctx = JobResultReadContext(
        config=ClientConfig(api_url="https://example.com/"),
        job_id="image-job",
        job_results=JobResults(root={"image": Link(href="/image.png")}),
        data_type=data_type,
    )
    registry = JobResultReaderRegistry.create_default()
    expected = xr.Dataset()
    with (
        patch.object(ImageReader, "is_usable", return_value=image_usable),
        patch("PIL.Image.open") as open_image,
        patch("xarray.open_dataset", return_value=expected) as open_dataset,
    ):
        result = await read_job_result(ctx, *registry.reader_types)

    assert result is expected
    open_image.assert_not_called()
    open_dataset.assert_called_once_with("/image.png")


def test_register():
    registry = JobResultReaderRegistry()
    assert len(registry.reader_types) == 0

    registry.register(DummyReader1)
    assert len(registry.reader_types) == 1
    registry.register(DummyReader2)
    assert len(registry.reader_types) == 2
    registry.register(DummyReader3)
    assert len(registry.reader_types) == 3
    assert registry.reader_types == (DummyReader3, DummyReader2, DummyReader1)

    registry.register(DummyReader1)
    assert len(registry.reader_types) == 3
    assert registry.reader_types == (DummyReader1, DummyReader3, DummyReader2)


def test_register_unregister():
    registry = JobResultReaderRegistry()
    unregister_1 = registry.register(DummyReader1)
    unregister_2 = registry.register(DummyReader2)
    assert callable(unregister_1)
    assert callable(unregister_2)
    assert unregister_1 is not unregister_2
    assert DummyReader1 in registry.reader_types
    assert DummyReader2 in registry.reader_types

    unregister_1()
    assert DummyReader1 not in registry.reader_types
    assert DummyReader2 in registry.reader_types

    unregister_2()
    assert DummyReader1 not in registry.reader_types
    assert DummyReader2 not in registry.reader_types

    # should not harm
    unregister_1()
    unregister_2()


def test_register_with_invalid_type():
    registry = JobResultReaderRegistry()
    with pytest.raises(
        TypeError,
        match="Type compatible with JobResultReader expected, but got <class 'int'>",
    ):
        # noinspection PyTypeChecker
        registry.register(int)


def test_clear():
    registry = JobResultReaderRegistry()
    registry.register(DummyReader1)
    registry.register(DummyReader2)
    registry.register(DummyReader3)
    assert len(registry.reader_types) == 3
    registry.clear()
    assert len(registry.reader_types) == 0
