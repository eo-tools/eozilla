#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from contextlib import ExitStack
from inspect import isawaitable
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
import xarray as xr
from PIL import Image

from cuiman.api import (
    AsyncClient,
    Client,
    ClientConfig,
    JobResultContext,
    JobResultResource,
)
from cuiman.api.opener import JobResultOpener, JobResultOpenError
from cuiman.api.resolver import (
    ComposedJobResultResolver,
    FolderResourceTransformer,
    ResourceEntry,
)
from cuiman.api.resolver.impl import StacResolver
from gavicore.models import JobInfo, JobResults, JobStatus, Link


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_exact_resource_and_receiving_configuration_without_lookup(client_type):
    resource = JobResultResource(
        id="selected",
        output_name="dataset",
        kind="asset",
        link=Link(href="s3://asset-store/data", type="text/csv"),
        media_type="text/csv; charset=utf-8",
        provenance={
            "job_id": "original-job",
            "service_url": "https://other.test",
            "output_value": {
                "href": "https://stac.test/item.json",
                "type": "application/geo+json",
            },
            "output_schema": {"type": "object"},
        },
    )
    snapshot = resource.model_dump_json()
    for marker in ["first-client", "second-client"]:
        client = _client(client_type, marker=marker)
        with _no_lookup(client):
            selected, context = await _open(
                client, resource, media_type="text/plain", chunks="auto"
            )
        assert selected is resource
        assert context.config is client.config
        assert context.options == {"marker": marker, "chunks": "auto"}
        assert context.media_type_for(selected) == "text/plain"
        assert resource.model_dump_json() == snapshot
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize(
    "options",
    [
        {"output_name": None},
        {"output_name": "dataset"},
        {"poll_interval": 1},
        {"poll_interval": None},
        {"timeout": 30},
        {"timeout": None},
    ],
)
async def test_job_only_arguments_rejected_before_io(client_type, options):
    client = _client(client_type)
    resource = JobResultResource(id="selected", output_name="x", kind="value", value=1)
    with (
        _no_lookup(client),
        patch.object(_InspectOpener, "accept", new=AsyncMock()) as accept,
    ):
        with pytest.raises(TypeError, match="Job-only arguments"):
            await _open(client, resource, **options)
        accept.assert_not_called()
    await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("target", [None, 42, {"href": "https://store.test/data"}])
async def test_unsupported_targets_rejected_before_io(client_type, target):
    client = _client(client_type)
    with (
        _no_lookup(client),
        pytest.raises(TypeError, match="string or JobResultResource"),
    ):
        await _open(client, target)
    await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("value", [None, False, 42, [1, 2], {"table": [1, 2]}])
async def test_linkless_values_are_passed_to_extensions(client_type, value):
    client = _client(client_type)
    resource = JobResultResource(
        id="selected", output_name="x", kind="value", value=value
    )
    with _no_lookup(client):
        selected, _ = await _open(client, resource)
    assert selected is resource and selected.has_value
    await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_job_form_keeps_positional_syntax_and_original_stac_output(client_type):
    client = _client(client_type)
    item = _item()
    factory = AsyncMock if client_type is AsyncClient else MagicMock
    with (
        patch.object(
            client,
            "get_job",
            new=factory(return_value=JobInfo(jobID="job", status=JobStatus.successful)),
        ) as get_job,
        patch.object(
            client,
            "get_job_results",
            new=factory(return_value=JobResults(root={"return_value": item})),
        ),
    ):
        selected, context = await _open(
            client,
            "https://looks.like/a/resource",
            None,
            dict,
            "application/json",
            0.01,
            30,
            marker="caller",
        )
        get_job.assert_called_once_with("https://looks.like/a/resource")
    assert selected.parent_id is None and selected.kind == "value"
    assert selected.value["assets"]["products"]["href"] == "s3://bucket/products"
    assert selected.link is None
    assert context.data_type is dict and context.media_type == "application/json"
    assert context.options["marker"] == "caller"
    await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("name", [None, "missing"])
async def test_job_output_ambiguity_and_missing_selection(client_type, name):
    client = _client(client_type)
    factory = AsyncMock if client_type is AsyncClient else MagicMock
    results = JobResults(root={"return_value": 1, "other": 2})
    with (
        patch.object(
            client,
            "get_job",
            new=factory(return_value=JobInfo(jobID="job", status=JobStatus.successful)),
        ),
        patch.object(client, "get_job_results", new=factory(return_value=results)),
    ):
        with pytest.raises(JobResultOpenError):
            await _open(client, job_id="job", output_name=name)
        selected, _ = await _open(client, job_id="job", output_name="other")
        assert selected.value == 2
    await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_resource_opening_respects_client_lifecycle(client_type):
    client = _client(client_type)
    await _close(client)
    resource = JobResultResource(id="selected", output_name="x", kind="value", value=1)
    with _no_lookup(client), pytest.raises(RuntimeError, match="Client is closed"):
        await _open(client, resource)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_selected_declared_descendant_opens_without_transforming_again(
    client_type,
):
    ctx = JobResultContext("dataset", _item())
    transformer = FolderResourceTransformer(
        entries=(
            ResourceEntry(key="summary", location="summary.csv", media_type="text/csv"),
        ),
        matches=lambda resource, ctx: resource.key == "products",
    )
    resolver = ComposedJobResultResolver(StacResolver(), (transformer,))
    listing = await resolver.resolve(ctx)
    selected = listing.select(key="summary")
    client = _client(client_type)
    with (
        _no_lookup(client),
        patch.object(
            transformer,
            "transform",
            side_effect=AssertionError("Opening repeated transformation"),
        ),
    ):
        opened, _ = await _open(client, selected)
    assert opened is selected and opened.link.href == "s3://bucket/products/summary.csv"
    assert opened.media_type == "text/csv"
    await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_builtin_readers_open_selected_csv_image_and_zarr(client_type, tmp_path):
    class BuiltinConfig(ClientConfig):
        pass

    client = client_type(config_type=BuiltinConfig, api_url="https://service.test")
    csv = tmp_path / "summary.csv"
    csv.write_text("value\n42\n", encoding="utf-8")
    resource = JobResultResource(
        id="csv",
        output_name="dataset",
        kind="asset",
        link=Link(href=csv.as_uri()),
        media_type="text/csv; charset=utf-8",
        provenance={"media_type": "application/geo+json"},
    )
    with _no_lookup(client):
        table = await _open(client, resource, data_type=pd.DataFrame)
    assert table["value"].tolist() == [42]
    image_file = tmp_path / "preview.png"
    Image.new("RGB", (2, 3)).save(image_file)
    resource = resource.with_updates(
        id="image", link=Link(href=image_file.as_uri()), media_type="image/png"
    )
    with _no_lookup(client):
        image = await _open(client, resource, data_type=Image.Image)
    assert image.size == (2, 3)
    image.close()
    zarr_file = tmp_path / "extensionless"
    expected = xr.Dataset({"value": ("x", [1, 2])})
    expected.to_zarr(zarr_file, consolidated=True, zarr_format=2)
    resource = resource.with_updates(
        id="zarr",
        link=Link(href=str(zarr_file)),
        media_type="application/zarr",
        metadata={"consolidated": True},
    )
    with _no_lookup(client):
        dataset = await _open(client, resource, data_type=xr.Dataset, chunks="auto")
    xr.testing.assert_equal(dataset.compute(), expected)
    dataset.close()
    await _close(client)


class _InspectOpener(JobResultOpener):
    id = "inspect"

    async def accept(self, resource, *, context):
        return True

    async def open(self, resource, *, context):
        return resource, context


def _client(client_type, marker="configured"):
    class Config(ClientConfig):
        extra_job_result_openers = (_InspectOpener,)

        @classmethod
        def get_job_result_opener_options(cls, resource, opener_id):
            return {"marker": marker}

    return client_type(config_type=Config, api_url="https://service.test")


def _no_lookup(client):
    stack = ExitStack()
    for name in ["get_job", "get_job_results", "get_process", "_request"]:
        stack.enter_context(
            patch.object(
                client,
                name,
                side_effect=AssertionError(f"Resource opening called {name}"),
            )
        )
    return stack


async def _open(client, *args, **kwargs):
    result = client.open_job_result(*args, **kwargs)
    return await result if isawaitable(result) else result


async def _close(client):
    result = client.close()
    if isawaitable(result):
        await result


def _item():
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "id": "item",
        "properties": {},
        "geometry": None,
        "links": [],
        "assets": {
            "products": {
                "href": "s3://bucket/products",
                "type": "application/x-directory",
            }
        },
    }
