"""Return-type and format contracts shared by both client modes and targets."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pystac
import pytest
import xarray as xr
from PIL import Image

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.reader import JobResultReadContext, JobResultReader, JobResultReadError
from cuiman.api.reader.reader import read_job_result
from gavicore.models.core import JobInfo, JobResults, JobStatus, Link


@pytest.fixture(params=[Client, AsyncClient], ids=["sync", "async"])
def client(request):
    class Config(ClientConfig):
        pass

    instance = request.param(
        config_type=Config, api_url="https://example.test", auth={"auth_type": "none"}
    )
    runner = asyncio.Runner()
    asynchronous = isinstance(instance, AsyncClient)

    def call(target, **options):
        result = instance.read_job_result(target, **options)
        return runner.run(result) if asynchronous else result

    yield instance, call, AsyncMock if asynchronous else Mock
    if asynchronous:
        runner.run(instance.close())
    else:
        instance.close()
    runner.close()


@pytest.fixture(params=["job", "asset"])
def read(request, client):
    instance, call, mock_type = client

    def read_target(href, media_type=None, **options):
        if request.param == "asset":
            return call(pystac.Asset(href, media_type=media_type), **options)
        with (
            patch.object(
                instance,
                "get_job",
                mock_type(
                    return_value=JobInfo(jobID="job", status=JobStatus.successful)
                ),
            ),
            patch.object(
                instance,
                "get_job_results",
                mock_type(
                    return_value=JobResults(
                        root={"result": Link(href=href, type=media_type)}
                    )
                ),
            ),
        ):
            return call("job", **options)

    return read_target


@pytest.mark.parametrize(
    "media_type", [None, "application/zarr", " Application/X-Zarr ; version=2"]
)
@pytest.mark.parametrize("requested", [None, xr.Dataset])
def test_zarr_dataset_stays_lazy(read, tmp_path, media_type, requested):
    path = tmp_path / ("data.zarr" if media_type is None else "misleading.nc")
    expected = xr.Dataset({"value": ("x", [1, 2, 3])}, coords={"x": [0, 1, 2]})
    expected.to_zarr(path, zarr_format=2)
    with read(path.as_uri(), media_type, data_type=requested, chunks={}) as actual:
        assert isinstance(actual, xr.Dataset)
        assert hasattr(actual["value"].data, "__dask_graph__")
        xr.testing.assert_equal(actual, expected)


@pytest.mark.parametrize("requested", [pd.DataFrame, int])
def test_zarr_unsupported_representation_raises(read, requested):
    with patch("xarray.open_dataset") as backend:
        with pytest.raises(JobResultReadError, match="No job result reader found"):
            read("https://data.test/data.zarr", "application/zarr", data_type=requested)
        backend.assert_not_called()


@pytest.mark.parametrize("engine", ["netcdf4", None])
def test_explicit_engine_overrides_inferred_backend(read, engine):
    expected = xr.Dataset({"value": ("x", [42])})
    close = Mock()
    expected.set_close(close)
    with patch("xarray.open_dataset", return_value=expected) as backend:
        actual = read(
            "https://data.test/data.nc",
            "application/zarr",
            data_type=xr.Dataset,
            engine=engine,
        )
    assert actual is expected
    close.assert_not_called()
    backend.assert_called_once_with("https://data.test/data.nc", engine=engine)
    actual.close()
    close.assert_called_once_with()


def test_unsupported_engine_raises(read):
    with pytest.raises(JobResultReadError):
        read(
            "https://data.test/data.zarr",
            "application/zarr",
            data_type=xr.Dataset,
            engine="unsupported-engine",
        )


def test_image_engine_selects_dataset_backend_instead_of_pillow(read):
    expected = xr.Dataset()
    with (
        patch("PIL.Image.open", side_effect=AssertionError("wrong backend")),
        patch("xarray.open_dataset", return_value=expected) as backend,
    ):
        assert (
            read("https://data.test/image.png", "image/png", engine="rasterio")
            is expected
        )
        backend.assert_called_once_with(
            "https://data.test/image.png", engine="rasterio"
        )


@pytest.mark.parametrize(
    "requested,media",
    [(Image.Image, "image/png"), (pystac.Catalog, "application/json")],
)
def test_unsupported_engine_and_representation_combination(read, requested, media):
    with pytest.raises(JobResultReadError):
        read("https://data.test/resource", media, data_type=requested, engine="zarr")


@pytest.mark.asyncio
async def test_image_reader_rejects_engine_from_client_policy():
    from cuiman.api.reader.impl import ImageReader

    class Config(ClientConfig):
        asset_reader_options = staticmethod(lambda ctx, reader_id: {"engine": "zarr"})

    ctx = JobResultReadContext(
        config=Config(),
        value=pystac.Asset("https://data.test/image.png", media_type="image/png"),
        location="https://data.test/image.png",
        _media_type="image/png",
        data_type=Image.Image,
    )
    with patch("PIL.Image.open") as backend:
        with pytest.raises(JobResultReadError):
            await read_job_result(ctx, ImageReader)
        backend.assert_not_called()


def test_media_type_overrides_conflicting_suffix(read):
    expected = pd.DataFrame({"value": [42]})
    with (
        patch("pandas.read_csv", return_value=expected) as csv,
        patch("pandas.read_parquet", side_effect=AssertionError("wrong format")),
    ):
        assert (
            read(
                "https://data.test/data.parquet",
                "Text/CSV; charset=utf-8",
                data_type=pd.DataFrame,
                sep=";",
            )
            is expected
        )
        csv.assert_called_once_with("https://data.test/data.parquet", sep=";")


def test_unsupported_media_type_does_not_use_suffix(read):
    with patch("pandas.read_csv") as csv:
        with pytest.raises(JobResultReadError):
            read(
                "https://data.test/data.csv",
                "application/unsupported",
                data_type=pd.DataFrame,
            )
        csv.assert_not_called()


def test_unsupported_dataset_format_does_not_use_zarr_suffix(read):
    with patch("xarray.open_dataset") as backend:
        with pytest.raises(JobResultReadError):
            read("https://data.test/data.zarr", "text/csv", data_type=xr.Dataset)
        backend.assert_not_called()


def test_custom_reader_must_return_requested_type(read, client):
    instance, _, _ = client

    class IncorrectReader(JobResultReader):
        reader_id = "incorrect"

        async def accept_job_result(self, ctx):
            return True

        async def read_job_result(self, ctx):
            return []

    unregister = instance.config.register_job_result_reader(IncorrectReader)
    try:
        with pytest.raises(JobResultReadError):
            read("https://data.test/value", data_type=dict, reader_id="incorrect")
    finally:
        unregister()


@pytest.mark.asyncio
@pytest.mark.parametrize("close_raises", [False, True])
async def test_wrong_result_is_closed_before_fallback(close_raises):
    wrong = Mock()
    if close_raises:
        wrong.close.side_effect = RuntimeError("close failed")

    class IncorrectReader(JobResultReader):
        reader_id = "incorrect"

        async def accept_job_result(self, ctx):
            return True

        async def read_job_result(self, ctx):
            return wrong

    class CorrectReader(IncorrectReader):
        reader_id = "correct"

        async def read_job_result(self, ctx):
            wrong.close.assert_called_once_with()
            return {"value": 42}

    ctx = JobResultReadContext(config=ClientConfig(), value=42, data_type=dict)
    with pytest.raises(JobResultReadError, match="Reader returned Mock; expected dict"):
        await read_job_result(ctx, IncorrectReader)
    wrong.close.reset_mock()
    assert await read_job_result(ctx, IncorrectReader, CorrectReader) == {"value": 42}


@pytest.mark.asyncio
async def test_invalid_requested_type_raises():
    ctx = JobResultReadContext(config=ClientConfig(), value=42, data_type="invalid")
    with pytest.raises(JobResultReadError, match="data_type must be a Python type"):
        await read_job_result(ctx)


@pytest.mark.asyncio
async def test_compatible_subclass_result_is_returned_without_closing():
    class Result(dict):
        close = Mock()

    result = Result(value=42)

    class Reader(JobResultReader):
        reader_id = "subclass"

        async def accept_job_result(self, ctx):
            return True

        async def read_job_result(self, ctx):
            return result

    ctx = JobResultReadContext(config=ClientConfig(), value=42, data_type=dict)
    assert await read_job_result(ctx, Reader) is result
    result.close.assert_not_called()
