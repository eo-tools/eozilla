#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest.mock import patch

import pytest
import xarray as xr
from PIL import Image

from cuiman.api.config import ClientConfig
from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenerRegistry,
)
from cuiman.api.opener.impl import (
    GeopandasDataFrameOpener,
    ImageOpener,
    PandasDataFrameOpener,
    XarrayDatasetOpener,
)
from cuiman.api.opener.opener import open_job_result
from gavicore.models import JobResults, Link


class DummyOpener1(JobResultOpener):
    async def accept_job_result(self, _ctx: JobResultOpenContext) -> bool:
        return False

    async def open_job_result(self, _ctx: JobResultOpenContext) -> Any:
        return None


class DummyOpener2(DummyOpener1):
    pass


class DummyOpener3(DummyOpener1):
    pass


def test_initially_empty():
    registry = JobResultOpenerRegistry()
    assert len(registry.opener_types) == 0


def test_default():
    registry = JobResultOpenerRegistry.create_default()
    assert registry.opener_types == (
        ImageOpener,
        XarrayDatasetOpener,
        PandasDataFrameOpener,
        GeopandasDataFrameOpener,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["png", "jpeg", "jpg"])
@pytest.mark.parametrize("media_type", [None, "image"])
async def test_default_opens_images_before_datasets(extension, media_type):
    href = f"/path/to/image.{extension}"
    if media_type == "image":
        media_type = "image/png" if extension == "png" else "image/jpeg"
    ctx = JobResultOpenContext(
        config=ClientConfig(api_url="https://example.com/"),
        job_id="image-job",
        job_results=JobResults(root={"image": Link(href=href, type=media_type)}),
    )
    expected = Image.new("RGB", (2, 2))
    registry = JobResultOpenerRegistry.create_default()
    with (
        patch("PIL.Image.open", return_value=expected) as open_image,
        patch("xarray.open_dataset") as open_dataset,
    ):
        result = await open_job_result(ctx, *registry.opener_types)

    assert result is expected
    open_image.assert_called_once_with(href)
    open_dataset.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("data_type,image_usable", [(None, False), (xr.Dataset, True)])
async def test_default_dataset_fallback(data_type, image_usable):
    ctx = JobResultOpenContext(
        config=ClientConfig(api_url="https://example.com/"),
        job_id="image-job",
        job_results=JobResults(root={"image": Link(href="/image.png")}),
        data_type=data_type,
    )
    registry = JobResultOpenerRegistry.create_default()
    expected = xr.Dataset()
    with (
        patch.object(ImageOpener, "is_usable", return_value=image_usable),
        patch("PIL.Image.open") as open_image,
        patch("xarray.open_dataset", return_value=expected) as open_dataset,
    ):
        result = await open_job_result(ctx, *registry.opener_types)

    assert result is expected
    open_image.assert_not_called()
    open_dataset.assert_called_once_with("/image.png")


def test_register():
    registry = JobResultOpenerRegistry()
    assert len(registry.opener_types) == 0

    registry.register(DummyOpener1)
    assert len(registry.opener_types) == 1
    registry.register(DummyOpener2)
    assert len(registry.opener_types) == 2
    registry.register(DummyOpener3)
    assert len(registry.opener_types) == 3
    assert registry.opener_types == (DummyOpener3, DummyOpener2, DummyOpener1)

    registry.register(DummyOpener1)
    assert len(registry.opener_types) == 3
    assert registry.opener_types == (DummyOpener1, DummyOpener3, DummyOpener2)


def test_register_unregister():
    registry = JobResultOpenerRegistry()
    unregister_1 = registry.register(DummyOpener1)
    unregister_2 = registry.register(DummyOpener2)
    assert callable(unregister_1)
    assert callable(unregister_2)
    assert unregister_1 is not unregister_2
    assert DummyOpener1 in registry.opener_types
    assert DummyOpener2 in registry.opener_types

    unregister_1()
    assert DummyOpener1 not in registry.opener_types
    assert DummyOpener2 in registry.opener_types

    unregister_2()
    assert DummyOpener1 not in registry.opener_types
    assert DummyOpener2 not in registry.opener_types

    # should not harm
    unregister_1()
    unregister_2()


def test_register_with_invalid_type():
    registry = JobResultOpenerRegistry()
    with pytest.raises(
        TypeError,
        match="Type compatible with JobResultOpener expected, but got <class 'int'>",
    ):
        # noinspection PyTypeChecker
        registry.register(int)


def test_clear():
    registry = JobResultOpenerRegistry()
    registry.register(DummyOpener1)
    registry.register(DummyOpener2)
    registry.register(DummyOpener3)
    assert len(registry.opener_types) == 3
    registry.clear()
    assert len(registry.opener_types) == 0
