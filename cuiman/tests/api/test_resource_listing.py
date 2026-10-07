"""Client listing views, budgets, and candidate assessment without data reads."""

import asyncio
import json
from inspect import isawaitable
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from cuiman.api import AsyncClient, Client, ClientConfig, JobResultContext
from cuiman.api.exceptions import ClientError, ClientWarning
from cuiman.api.metadata import DiscoveryLimits, MetadataResponse
from cuiman.api.opener import JobResultOpener, JobResultStatusError
from cuiman.api.opener.opener import assess_job_result
from cuiman.api.resolver import JobResultResolver
from cuiman.api.resources import (
    JobResultResource,
    JobResultResourceListing,
    ResourceNotFoundError,
)
from examples.guides.cuiman.resolvers import ProductFolderResolver
from gavicore.models import ApiError, JobInfo, JobResults, JobStatus, ProcessDescription
from wraptile.services.local.testing import service


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_default_item_asset_and_parent_views(client_type):
    client = _client(
        client_type, {"result": _item(), "report": {"href": "report.txt"}, "null": None}
    )
    try:
        listing = await _list(client)
        assert [r.kind for r in listing] == ["asset", "link", "value"]
        assert set(listing.output_states) == {"result", "report", "null"}
        assert listing.discovery_state == "complete"
        data = listing.select(key="data")
        assert data.link.href == "https://metadata.test/inline/data.csv"
        assert data.capabilities.opener.state == "available"
        assert data.capabilities.preview.state == "unknown"
        assert (
            listing.select(output_name="report").link.href
            == "https://service.test/jobs/job/report.txt"
        )
        assert listing.select(output_name="null").has_value
        items = await _list(client, output_name="result", kind="stac-item")
        assert len(items) == 1
        members = await _list(client, parent_id=items[0].id)
        assert [r.id for r in members] == [data.id]
        assert set(members.output_states) == {"result"}
        assert (await _list(client, parent_id=data.id)).discovery_state == "complete"
        assert len(await _list(client, parent_id=data.id)) == 0
        assert client.get_job.call_count == 5
        assert client.get_job_results.call_count == 5
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_declared_folder_members_and_exact_opening(client_type, tmp_path):
    folder = tmp_path / "products"
    (folder / "tables").mkdir(parents=True)
    (folder / "tables/observations.csv").write_text("date,ndvi\n2026-09-01,0.75\n")
    item = _item()
    item["assets"] = {
        "products": {"href": folder.as_uri(), "type": "application/x-directory"}
    }
    client = _client(client_type, {"result": item}, resolvers=(ProductFolderResolver,))
    factory = AsyncMock if client_type is AsyncClient else MagicMock
    client.get_job.return_value.processID = "simulate_stac_item"
    client.get_process = factory(
        return_value=service.process_registry.get("simulate_stac_item").description
    )
    try:
        listing = await _list(client)
        assert [r.key for r in listing] == ["products", "tables", "observations"]
        tables = await _list(client, parent_id=listing.select(key="products").id)
        assert [r.key for r in tables] == ["tables"]
        files = await _list(client, parent_id=tables[0].id)
        assert [r.key for r in files] == ["observations"]
        before = client.get_job.call_count
        table = client.open_job_result(files[0], data_type=pd.DataFrame)
        if isawaitable(table):
            table = await table
        assert table.to_dict("records") == [{"date": "2026-09-01", "ndvi": 0.75}]
        assert client.get_job.call_count == before
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("status", ["accepted", "running", "failed", "dismissed"])
async def test_unsuccessful_job_fails_once_without_results_or_polling(
    client_type, status
):
    client = _client(client_type, {})
    client.get_job.return_value.status = JobStatus(status)
    try:
        with pytest.raises(JobResultStatusError):
            await _list(client)
        client.get_job.assert_called_once_with("job")
        client.get_job_results.assert_not_called()
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize(
    "options",
    [
        {"output_name": ""},
        {"parent_id": 1},
        {"kind": []},
        {"data_type": "pandas"},
        {"limits": {}},
        {"refresh": 1},
    ],
)
async def test_invalid_arguments_fail_before_io(client_type, options):
    client = _client(client_type, {})
    try:
        with pytest.raises(TypeError):
            await _list(client, **options)
        client.get_job.assert_not_called()
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_empty_unsupported_missing_and_closed_views(client_type):
    client = _client(
        client_type,
        {
            "empty": {
                "type": "FeatureCollection",
                "stac_version": "1.1.0",
                "features": [],
            },
            "plain": 42,
        },
    )
    factory = AsyncMock if client_type is AsyncClient else MagicMock
    client.get_job.return_value.processID = "empty-stac"
    client.get_process = factory(
        return_value=ProcessDescription(
            id="empty-stac",
            version="1",
            outputs={
                "empty": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "type": {"enum": ["FeatureCollection"]},
                            "features": {
                                "items": {
                                    "$ref": "https://schemas.stacspec.org/v1.1.0/item-spec/json-schema/item.json"
                                }
                            },
                        },
                    }
                }
            },
        )
    )
    try:
        empty = await _list(client, output_name="empty", kind="stac-item")
        assert len(empty) == 0 and empty.discovery_state == "complete"
        unsupported = await _list(client, output_name="plain", kind="stac-item")
        assert len(unsupported) == 0 and unsupported.discovery_state == "error"
        assert unsupported.diagnostics[0].code == "unsupported-kind"
        assert len(await _list(client, kind="custom-kind")) == 0
        for options in [{"output_name": "missing"}, {"parent_id": "missing"}]:
            with pytest.raises(ResourceNotFoundError):
                await _list(client, **options)
        client.get_job.reset_mock()
    finally:
        await _close(client)
    with pytest.raises(RuntimeError, match="closed"):
        await _list(client)
    client.get_job.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_cache_refresh_limits_and_client_isolation(client_type):
    document = _item()
    fetch = AsyncMock(
        side_effect=lambda href, **kwargs: MetadataResponse(
            json.dumps(document).encode(), "https://redirect.test/item.json"
        )
    )
    outputs = {
        "first": {
            "href": "https://source.test/item.json",
            "type": "application/geo+json",
        },
        "second": {
            "href": "https://source.test/item.json",
            "type": "application/geo+json",
        },
    }
    client = _client(client_type, outputs, fetch=fetch)
    other = _client(client_type, outputs, fetch=fetch)
    try:
        first = await _list(client)
        assert fetch.await_count == 1
        assert [r.link.href for r in first] == ["https://redirect.test/data.csv"] * 2
        document["assets"]["data"]["href"] = "new.csv"
        cached = await _list(client)
        assert fetch.await_count == 1
        assert [r.link.href for r in cached] == [r.link.href for r in first]
        refreshed = await _list(client, refresh=True)
        assert fetch.await_count == 2
        assert [r.id for r in first] == [r.id for r in refreshed]
        assert refreshed[0].link.href == "https://redirect.test/new.csv"
        await _list(other)
        await _list(client, limits=DiscoveryLimits(max_requests=1))
        await _list(client, job_id="another")
        assert fetch.await_count == 5
        # Candidate assessment is recomputed even when documents are cached.
        client.config.get_job_result_opener_registry().clear()
        unavailable = await _list(client, job_id="another")
        assert unavailable[0].capabilities.opener.state == "unavailable"
        assert fetch.await_count == 5
    finally:
        await _close(client)
        await _close(other)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_failures_and_shared_request_budget_preserve_other_outputs(client_type):
    fetch = AsyncMock(side_effect=RuntimeError("SECRET"))
    outputs = {
        "failed": {"href": "https://source.test/a.json", "type": "application/json"},
        "limited": {"href": "https://source.test/b.json", "type": "application/json"},
        "ok": None,
    }
    client = _client(client_type, outputs, fetch=fetch)
    try:
        listing = await _list(client, limits=DiscoveryLimits(max_requests=1))
        assert listing.discovery_state == "partial"
        assert listing.output_states["failed"].discovery_state == "error"
        assert listing.output_states["limited"].discovery_state == "partial"
        assert listing.output_states["ok"].discovery_state == "complete"
        assert fetch.await_count == 1
        assert "SECRET" not in listing.model_dump_json()
        await _list(client, limits=DiscoveryLimits(max_requests=1))
        assert (
            fetch.await_count == 2
        )  # cached failure costs no requests; next URL gets this call's budget
        await _list(client, limits=DiscoveryLimits(max_requests=1), refresh=True)
        assert fetch.await_count == 3
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
async def test_global_resource_budget_and_optional_schema_failure(client_type):
    client = _client(client_type, {"first": _item(), "second": _item(), "third": 1})
    factory = AsyncMock if client_type is AsyncClient else MagicMock
    client.get_job.return_value.processID = "unavailable"
    client.get_process = factory(
        side_effect=ClientError("SECRET", ApiError(type="error", title="failure"))
    )
    try:
        with pytest.warns(ClientWarning, match="description unavailable"):
            listing = await _list(client, limits=DiscoveryLimits(max_resources=3))
        assert listing.discovery_state == "partial"
        assert len(listing) == 1  # hidden containers still consume expansion budget
        assert listing.output_states["second"].discovery_state == "partial"
        assert listing.output_states["third"].discovery_state == "unresolved"
        assert "SECRET" not in listing.model_dump_json()
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["return-type", "ownership"])
async def test_bad_extension_falls_back_without_losing_sibling(bad):
    class Broken(JobResultResolver):
        async def accept(self, ctx):
            return ctx.output_name == "broken"

        async def resolve(self, ctx):
            return (
                None
                if bad == "return-type"
                else JobResultResourceListing(
                    resources=(
                        JobResultResource(
                            id="wrong", output_name="other", kind="value", value=1
                        ),
                    )
                )
            )

    client = _client(AsyncClient, {"broken": None, "ok": 1}, resolvers=(Broken,))
    try:
        listing = await _list(client)
        assert [r.output_name for r in listing] == ["broken", "ok"]
        assert listing.output_states["broken"].discovery_state == "error"
        assert listing.select(output_name="broken").has_value
    finally:
        await _close(client)


@pytest.mark.asyncio
async def test_catalog_stays_deferred_and_collection_keeps_concrete_assets():
    collection = {
        "type": "Collection",
        "stac_version": "1.1.0",
        "id": "collection",
        "description": "Demo",
        "extent": {},
        "license": "proprietary",
        "links": [{"rel": "item", "href": "remote.json"}],
        "assets": {"data": {"href": "s3://bucket/data.csv"}},
    }
    fetch = AsyncMock(side_effect=AssertionError("must not traverse"))
    client = _client(AsyncClient, {"result": collection}, fetch=fetch)
    try:
        listing = await _list(client)
        assert [r.kind for r in listing] == ["stac-collection", "asset"]
        assert listing.discovery_state == "complete"
        members = await _list(client, parent_id=listing[0].id)
        assert len(members) == 1 and members.discovery_state == "partial"
        assert members.diagnostics[-1].code == "deferred-traversal"
        fetch.assert_not_called()
    finally:
        await _close(client)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode, expected",
    [
        ("missing", "unavailable"),
        ("reject", "unavailable"),
        ("accept", "available"),
        ("fail", "unknown"),
        ("mixed", "available"),
    ],
)
async def test_assessment_states_isolation_and_no_access(mode, expected):
    class Reader(JobResultOpener):
        id = "test-reader"

        @classmethod
        def is_usable(cls):
            return mode != "missing"

        async def accept(self, resource, *, context):
            context.options["mutated"] = True
            if mode in {"fail", "mixed"}:
                raise RuntimeError("SECRET")
            return mode == "accept"

        async def open(self, resource, *, context):
            raise AssertionError("assessment must not open data")

    class Good(Reader):
        async def accept(self, resource, *, context):
            assert "mutated" not in context.options
            return True

    provider = MagicMock()
    provider.resolve = AsyncMock(side_effect=AssertionError("no access"))

    class Config(ClientConfig):
        job_result_access_provider = provider

    context = JobResultContext(
        config=Config(), data_type=pd.DataFrame, options={"marker": 1}
    )
    resource = JobResultResource(
        id="x",
        output_name="result",
        kind="value",
        value=None,
        open_hints={"test-reader": {"unsupported": "hint"}},
    )
    types = (Reader, Good, Good) if mode == "mixed" else (Reader,)
    assessed = await assess_job_result(resource, *types, context=context)
    assert assessed.capabilities.opener.state == expected
    assert assessed.capabilities.preview.state == "unknown"
    assert context.options == {"marker": 1}
    assert resource.capabilities.opener.state == "unknown"
    assert "SECRET" not in assessed.model_dump_json()
    if expected == "available":
        assert len(assessed.capabilities.opener.candidates) == 1
    provider.resolve.assert_not_called()


@pytest.mark.asyncio
async def test_zero_rows_and_exact_budget_preserve_output_states():
    client = _client(AsyncClient, {})
    try:
        empty = await _list(client)
        assert empty.discovery_state == "complete" and not empty.output_states
        client.get_job_results.return_value = JobResults(
            root={"first": None, "second": 1}
        )
        listing = await _list(client, limits=DiscoveryLimits(max_resources=1))
        assert len(listing) == 1
        assert listing.output_states["second"].discovery_state == "unresolved"
        assert listing.diagnostics[0].code == "resource-limit"
    finally:
        await _close(client)


@pytest.mark.asyncio
async def test_malformed_source_locations_and_qualified_inline_values():
    client = _client(
        AsyncClient,
        {
            "qualified": {"mediaType": "application/geo+json", "value": _item()},
            "links": {"links": 42},
            "self": {"links": [{"rel": "self", "href": "https://["}]},
            "bad": {"href": "https://["},
        },
    )
    try:
        listing = await _list(client)
        assert (
            listing.select(output_name="qualified").link.href
            == "https://metadata.test/inline/data.csv"
        )
        assert listing.output_states["bad"].discovery_state == "error"
        assert listing.select(output_name="bad").link.href == "https://["
        assert listing.output_states["self"].discovery_state == "complete"
        assert listing.output_states["links"].discovery_state == "complete"
        with pytest.raises(TypeError):
            await _list(client, job_id=None)
    finally:
        await _close(client)


@pytest.mark.asyncio
async def test_extension_container_with_malformed_navigation_is_inspectable():
    class Container(JobResultResolver):
        async def accept(self, ctx):
            return True

        async def resolve(self, ctx):
            return JobResultResourceListing(
                resources=(
                    JobResultResource(
                        id="container",
                        output_name=ctx.output_name,
                        kind="stac-catalog",
                        value=ctx.value,
                        metadata={"stac": {"links": None}},
                    ),
                ),
                discovery_state="complete",
            )

    client = _client(AsyncClient, {"result": None}, resolvers=(Container,))
    try:
        listing = await _list(client, parent_id="container")
        assert len(listing) == 0 and listing.discovery_state == "complete"
    finally:
        await _close(client)


@pytest.mark.asyncio
async def test_cancellation_propagates_from_assessment():
    class Cancelled(JobResultOpener):
        async def accept(self, resource, *, context):
            raise asyncio.CancelledError()

        async def open(self, resource, *, context):
            pass

    with pytest.raises(asyncio.CancelledError):
        await assess_job_result(
            JobResultResource(id="x", output_name="x", kind="value", value=1),
            Cancelled,
            context=JobResultContext(output_name="x"),
        )


def _client(client_type, outputs, *, fetch=None, resolvers=()):
    class Config(ClientConfig):
        job_result_metadata_fetcher = fetch
        extra_job_result_resolvers = resolvers

    client = client_type(
        config_type=Config, api_url="https://service.test", auth={"auth_type": "none"}
    )
    factory = AsyncMock if client_type is AsyncClient else MagicMock
    client.get_job = factory(return_value=JobInfo(jobID="job", status="successful"))
    client.get_job_results = factory(return_value=JobResults(root=outputs))
    return client


async def _list(client, job_id="job", **kwargs):
    result = client.list_job_result_resources(job_id, **kwargs)
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
        "links": [{"rel": "self", "href": "https://metadata.test/inline/item.json"}],
        "assets": {"data": {"href": "data.csv", "type": "text/csv"}},
    }
