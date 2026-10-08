"""Exact-Asset semantics shared by synchronous and asynchronous clients."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx2
import pandas as pd
import pystac
import pytest
import xarray as xr
from PIL import Image

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from cuiman.api.opener import (
    JobResultOpenContext,
    JobResultOpener,
    JobResultOpenError,
)
from cuiman.api.opener.impl import StacJobResultOpener
from cuiman.api.opener.impl.base import PathOpener
from cuiman.api.opener.opener import open_job_result
from gavicore.models import JobInfo, JobResults, JobStatus, ProcessRequest
from procodile import Job
from wraptile.services.local.testing import service


class InspectOpener(JobResultOpener):
    async def accept_job_result(self, ctx):
        return ctx.options.get("inspect_context", False)

    async def open_job_result(self, ctx):
        return ctx


@pytest.fixture(params=[False, True], ids=["sync", "async"])
def client(request, tmp_path):
    asynchronous = request.param
    runner = asyncio.Runner()

    class Config(ClientConfig):
        extra_job_result_openers = (InspectOpener,)

    instance = (AsyncClient if asynchronous else Client)(
        api_url="https://receiving.test",
        auth={"auth_type": "none"},
        config_type=Config,
        config_path=str(tmp_path / "client.yaml"),
    )
    mock_type = AsyncMock if asynchronous else Mock
    with (
        patch.object(
            instance,
            "get_job",
            mock_type(side_effect=AssertionError("job lookup forbidden")),
        ),
        patch.object(
            instance,
            "get_job_results",
            mock_type(side_effect=AssertionError("results lookup forbidden")),
        ),
        patch.object(
            instance,
            "get_process",
            mock_type(side_effect=AssertionError("process lookup forbidden")),
        ),
        patch.object(
            pystac.stac_io.DefaultStacIO,
            "read_json",
            side_effect=AssertionError("metadata read forbidden"),
        ),
    ):

        def call(*args, **kwargs):
            result = instance.open_job_result(*args, **kwargs)
            return runner.run(result) if asynchronous else result

        yield instance, call
    if asynchronous:
        runner.run(instance.close())
    else:
        instance.close()
    runner.close()


def owner(asset, base="https://data.test/items/item.json"):
    item = pystac.Item(
        "source", None, None, datetime(2026, 1, 1, tzinfo=timezone.utc), {}
    )
    item.set_self_href(base)
    item.add_asset("chosen", asset)
    item.add_asset(
        "sibling",
        pystac.Asset("https://must-not-read.test/data.csv", media_type="text/csv"),
    )
    return item


@pytest.mark.parametrize(
    "option,value",
    [
        ("output_name", None),
        ("output_name", "data"),
        ("poll_interval", None),
        ("poll_interval", DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL),
        ("timeout", None),
        ("timeout", DEFAULT_OPEN_JOB_RESULT_TIMEOUT),
    ],
)
def test_job_only_arguments_rejected_before_dispatch(client, option, value):
    _, call = client
    asset = pystac.Asset("data.csv")
    owning = owner(asset)
    with (
        patch.object(
            owning, "get_self_href", side_effect=AssertionError("resolution forbidden")
        ),
        patch.object(
            InspectOpener,
            "accept_job_result",
            side_effect=AssertionError("dispatch forbidden"),
        ),
    ):
        with pytest.raises(TypeError, match=option):
            call(asset, **{option: value})
    with pytest.raises(TypeError, match="output_name"):
        call(asset, None)


@pytest.mark.parametrize("target", [None, 17, Path("data.csv"), {}, [], object()])
def test_unsupported_target_rejected(client, target):
    _, call = client
    with patch.object(
        InspectOpener,
        "accept_job_result",
        side_effect=AssertionError("dispatch forbidden"),
    ):
        with pytest.raises(TypeError, match="job ID string or a pystac.Asset"):
            call(target)


def test_native_item_is_not_an_opening_target(client):
    _, call = client
    with pytest.raises(TypeError):
        call(owner(pystac.Asset("data.csv")))


def test_exact_context_format_owner_and_receiving_client(client):
    instance, call = client
    asset = pystac.Asset(
        "reports/chosen.csv?signature=private",
        media_type="text/csv; charset=utf-8",
        title="Report",
        extra_fields={
            "foreign:client": "https://producing.test",
            "x-options": {"unsafe": True},
        },
    )
    owning = owner(asset)
    original = deepcopy(owning.to_dict())
    with patch.object(
        owning, "get_root", side_effect=AssertionError("navigation forbidden")
    ):
        ctx = call(
            job_id_or_asset=asset,
            inspect_context=True,
            data_type=pd.DataFrame,
            delimiter=";",
        )
        assert ctx.value is asset
        assert ctx.config is instance.config
        assert (
            ctx.location
            == "https://data.test/items/reports/chosen.csv?signature=private"
        )
        assert ctx.output_media_type == "text/csv; charset=utf-8"
        assert ctx.options == {"inspect_context": True, "delimiter": ";"}
        assert ctx.job_id is None and ctx.job_results is None
        assert (
            ctx.output_name is None
            and ctx.output_description is None
            and ctx.process_description is None
        )
        override = call(
            asset, inspect_context=True, media_type="application/json; charset=UTF-8"
        )
        assert override.output_media_type == "application/json; charset=UTF-8"
        assert asset.media_type == "text/csv; charset=utf-8"
    assert owning.to_dict() == original


@pytest.mark.parametrize("base", [None, "relative/item.json"])
def test_missing_absolute_owner_base_fails(client, base):
    _, call = client
    asset = pystac.Asset("data.csv")
    if base is not None:
        owning = owner(asset)
        owning.get_self_href = Mock(return_value=base)
    with pytest.raises(JobResultOpenError, match="owner.*base"):
        call(asset)


def test_owner_without_self_link_fails(client):
    _, call = client
    asset = pystac.Asset("data.csv")
    owning = owner(asset)
    owning.remove_links("self")
    with pytest.raises(JobResultOpenError, match="owner.*base"):
        call(asset)


@pytest.mark.parametrize("href", ["", None])
def test_invalid_href_fails(client, href):
    _, call = client
    asset = pystac.Asset("placeholder")
    asset.href = href
    with pytest.raises(JobResultOpenError, match="non-empty"):
        call(asset)


def test_absolute_asset_does_not_consult_owner(client):
    _, call = client
    asset = pystac.Asset(
        "https://store.test/data.zarr?signature=private", media_type="application/zarr"
    )
    owning = owner(asset)
    with patch.object(
        owning, "get_self_href", side_effect=AssertionError("owner lookup forbidden")
    ):
        assert call(asset, inspect_context=True).location == asset.href


@pytest.mark.parametrize("href", ["file:relative.csv", "https:relative.csv"])
def test_non_absolute_uri_does_not_guess_a_base(client, href):
    _, call = client
    asset = pystac.Asset("placeholder")
    asset.href = href
    owner(asset)
    with pytest.raises(JobResultOpenError, match="URI scheme must be absolute"):
        call(asset)


def test_closed_client_rejects_asset_before_dispatch(client):
    instance, call = client
    with (
        patch.object(instance, "_closed", True),
        patch.object(
            InspectOpener,
            "accept_job_result",
            side_effect=AssertionError("dispatch forbidden"),
        ),
    ):
        with pytest.raises(RuntimeError, match="closed"):
            call(pystac.Asset("https://data.test/data.csv"), inspect_context=True)


def test_async_asset_respects_owner_loop(client):
    instance, call = client
    asset = pystac.Asset("https://data.test/data.csv")
    call(asset, inspect_context=True)
    if isinstance(instance, AsyncClient):
        with pytest.raises(RuntimeError, match="owning event loop"):
            asyncio.run(instance.open_job_result(asset, inspect_context=True))


def test_independent_asset_without_media_type_uses_own_suffix(client, tmp_path):
    _, call = client
    path = tmp_path / "report.csv"
    path.write_text("value\n42\n", encoding="utf-8")
    assert call(pystac.Asset(path.as_uri()), data_type=pd.DataFrame)[
        "value"
    ].tolist() == [42]


def test_collection_asset_uses_asset_media_type(client):
    _, call = client
    collection = pystac.Collection(
        "collection",
        "description",
        pystac.Extent(
            pystac.SpatialExtent([[-180, -90, 180, 90]]),
            pystac.TemporalExtent([[None, None]]),
        ),
    )
    collection.set_self_href("https://data.test/collection.json")
    asset = pystac.Asset("report.csv", media_type="text/csv")
    collection.add_asset("report", asset)
    ctx = call(asset, inspect_context=True)
    assert ctx.location == "https://data.test/report.csv"
    assert ctx.output_media_type == "text/csv"


def test_root_relative_and_storage_locations(client):
    _, call = client
    asset = pystac.Asset("/reports/data.csv", media_type="text/csv")
    owner(asset)
    assert (
        call(asset, inspect_context=True).location
        == "https://data.test/reports/data.csv"
    )
    asset = pystac.Asset(
        "../products/data.zarr?signature=asset", media_type="application/zarr"
    )
    owner(asset, "s3://bucket/items/item.json?signature=metadata")
    assert (
        call(asset, inspect_context=True).location
        == "s3://bucket/products/data.zarr?signature=asset"
    )


@pytest.mark.parametrize("file_uri", [False, True])
def test_actual_csv_with_spaces_file_uris_and_native_paths(client, tmp_path, file_uri):
    _, call = client
    path = tmp_path / "products with spaces" / "report.csv"
    path.parent.mkdir()
    path.write_text("value\n42\n", encoding="utf-8")
    asset = pystac.Asset(
        path.as_uri() if file_uri else str(path), media_type="text/csv; charset=utf-8"
    )
    original_href = asset.href
    assert call(asset, data_type=pd.DataFrame)["value"].tolist() == [42]
    assert asset.href == original_href


def test_relative_file_asset_resolves_from_owner(client, tmp_path):
    _, call = client
    path = tmp_path / "report with spaces.csv"
    path.write_text("value\n42\n", encoding="utf-8")
    asset = pystac.Asset("report%20with%20spaces.csv", media_type="text/csv")
    owner(asset, (tmp_path / "item.json").as_uri())
    assert call(asset, data_type=pd.DataFrame)["value"].tolist() == [42]


def test_asset_format_beats_suffix_and_preserves_parameters(client):
    _, call = client
    asset = pystac.Asset(
        "https://data.test/opaque.parquet?signature=private",
        media_type="text/csv; charset=utf-8",
    )
    expected = pd.DataFrame({"value": [42]})
    with (
        patch("pandas.read_csv", return_value=expected) as read_csv,
        patch("pandas.read_parquet", side_effect=AssertionError("wrong format")),
    ):
        assert call(asset, data_type=pd.DataFrame, sep=";") is expected
        read_csv.assert_called_once_with(asset.href, sep=";")
    assert asset.media_type == "text/csv; charset=utf-8"


def test_json_asset_is_data_without_metadata_rediscovery(client):
    _, call = client
    asset = pystac.Asset("https://data.test/table.json", media_type="application/json")
    expected = pd.DataFrame({"value": [42]})
    with (
        patch.object(
            StacJobResultOpener,
            "open_job_result",
            side_effect=AssertionError("STAC rediscovery forbidden"),
        ),
        patch("pandas.read_json", return_value=expected) as reader,
    ):
        assert call(asset, data_type=pd.DataFrame) is expected
        reader.assert_called_once_with(asset.href)


def test_image_asset_and_extensionless_media_type(client, tmp_path):
    _, call = client
    path = tmp_path / "image without suffix"
    Image.new("RGB", (2, 2), "red").save(path, format="PNG")
    with call(
        pystac.Asset(path.as_uri(), media_type="image/png; profile=test"),
        data_type=Image.Image,
    ) as image:
        assert image.size == (2, 2) and image.getpixel((0, 0)) == (255, 0, 0)


def test_string_url_still_identifies_job(client):
    instance, call = client
    mock_type = AsyncMock if isinstance(instance, AsyncClient) else Mock
    with (
        patch.object(
            instance,
            "get_job",
            mock_type(return_value=JobInfo(jobID="url", status=JobStatus.successful)),
        ),
        patch.object(
            instance,
            "get_job_results",
            mock_type(return_value=JobResults(root={"only": 17})),
        ),
    ):
        ctx = call(
            job_id_or_asset="https://looks-like-data.test/data.csv",
            inspect_context=True,
        )
        instance.get_job.assert_called_once_with(
            "https://looks-like-data.test/data.csv"
        )
        assert ctx.job_id == "https://looks-like-data.test/data.csv" and ctx.value == 17


@pytest.mark.parametrize("process_id", ["create_inline_stac", "create_linked_stac"])
def test_demo_metadata_to_exact_asset(client, tmp_path, monkeypatch, process_id):
    _, call = client
    directory = tmp_path / "products"
    monkeypatch.setenv("EOZILLA_TESTING_STAC_DIR", str(directory))
    monkeypatch.setenv("EOZILLA_TESTING_STAC_URL", "https://metadata.test/testing-stac")
    process = service.process_registry.get(process_id)
    results = Job.create(process, ProcessRequest(inputs={"item_count": 2})).run()
    original = deepcopy(results.model_dump(mode="json"))

    def handle(request):
        relative = request.url.path.removeprefix("/testing-stac/")
        return httpx2.Response(200, content=(directory / relative).read_bytes())

    # Metadata from a foreign configuration is read explicitly first.
    class ProducerConfig(ClientConfig):
        @staticmethod
        def stac_io_factory(config):
            io = pystac.StacIO.default()
            io.read_json = Mock(
                side_effect=lambda href: handle(httpx2.Request("GET", href)).json()
            )
            return io

    ctx = JobResultOpenContext(
        config=ProducerConfig(api_url="https://producing.test"),
        job_results=results,
        output_name="item_collection",
    )
    items = asyncio.run(open_job_result(ctx, StacJobResultOpener))
    selected = items[1].assets["data"]
    parsed_original = deepcopy(items.to_dict())

    def read_data(href, **options):
        assert href == selected.href
        relative = href.removeprefix("https://metadata.test/testing-stac/")
        return xr.open_zarr(str(directory / relative))

    # Replace only the reader's HTTP boundary; consume the real generated Zarr.
    with patch("xarray.open_dataset", side_effect=read_data) as reader:
        with call(selected, data_type=xr.Dataset, engine="zarr") as dataset:
            assert dataset["ndvi"].values.tolist() == [[1, 2], [3, 4]]
        reader.assert_called_once_with(selected.href, engine="zarr")
    assert items.to_dict() == parsed_original
    assert results.model_dump(mode="json") == original


@pytest.mark.parametrize(
    "href,expected",
    [
        ("https://host.test/path/no-suffix?file=data.csv", ""),
        ("https://host.test/data.csv?signature=abc.def#fragment", ".csv"),
        ("s3://bucket/data.zarr?signature=abc", ".zarr"),
        ("data", ""),
        ("./folder.with.dots/data", ""),
    ],
)
def test_suffix_detection(href, expected):
    assert PathOpener.get_filename_ext(href) == expected
