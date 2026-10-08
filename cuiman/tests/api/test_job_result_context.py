from copy import deepcopy
from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, patch

import pytest
import xarray as xr

from cuiman.api import JobResultContext
from cuiman.api.config import ClientConfig
from cuiman.api.context import describe_job_output
from cuiman.api.opener import JobResultOpenError
from cuiman.api.opener.impl import PandasDataFrameOpener, XarrayDatasetOpener
from cuiman.api.opener.opener import open_job_result
from cuiman.api.resolver import (
    ComposedJobResultResolver,
    DiscoveryLimits,
    FolderResourceTransformer,
    MetadataLoader,
    MetadataResponse,
    resolve_job_result,
)
from cuiman.api.resolver.impl import StacResolver, ValueResolver
from cuiman.api.resources import JobResultResource
from gavicore.models import (
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        0,
        [],
        {"table": [1]},
        QualifiedValue(value=[1], mediaType="application/json"),
        Link(href="https://store.test/item.json", type="application/geo+json"),
    ],
)
async def test_describe_original_output_preserves_values_and_provenance(value):
    results = JobResults(root={"selected": value})
    description = ProcessDescription(
        id="process",
        version="1",
        outputs={
            "selected": OutputDescription(title="Selected", schema={"type": "object"})
        },
    )
    resource = await describe_job_output(
        "job",
        results,
        None,
        service_url="https://service.test",
        process_description=description,
    )
    assert resource.output_name == "selected" and resource.parent_id is None
    assert resource.provenance["process_id"] == "process"
    assert resource.title == "Selected"
    assert resource.has_value == (not isinstance(value, Link))
    assert results.root["selected"] == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "results,name",
    [
        (JobResults(), None),
        (JobResults(root={"a": 1, "return_value": 2}), None),
        (JobResults(root={"a": 1}), "missing"),
    ],
)
async def test_ambiguous_empty_and_missing_outputs_are_errors(results, name):
    with pytest.raises(JobResultOpenError):
        await describe_job_output("job", results, name)


def test_options_precedence_merging_clearing_and_hint_validation():
    class Config(ClientConfig):
        @classmethod
        def get_job_result_opener_options(cls, resource, opener_id):
            assert resource.id == "r" and opener_id == "xarray"
            return {"chunks": 2, "backend_kwargs": {"group": "configured"}}

    resource = _resource(
        open_hints={
            "xarray": {
                "chunks": "auto",
                "backend_kwargs": {
                    "consolidated": True,
                    "storage_options": {"anon": True},
                },
                "danger": "SECRET",
                "engine": "evil.module",
                "decode_times": "wrong",
            },
            "pandas": {"sep": ";"},
        }
    )
    caller = {"chunks": None, "backend_kwargs": {"group": "caller"}}
    original = deepcopy(caller)
    context = JobResultContext(config=Config(), options=caller, media_type="text/plain")
    candidate = context.for_opener(resource, XarrayDatasetOpener())
    assert candidate.options == {
        "chunks": None,
        "backend_kwargs": {
            "consolidated": True,
            "group": "caller",
            "storage_options": {"anon": True},
        },
    }
    assert candidate.option_sources["chunks"] == "caller"
    assert len(candidate.diagnostics) == 3 and "SECRET" not in str(
        candidate.diagnostics
    )
    assert caller == original
    assert resource.media_type == "application/zarr"
    assert candidate.media_type_for(resource) == "text/plain"
    assert "sep" not in candidate.options
    assert (
        context.for_opener(
            resource.with_updates(open_hints={"xarray": []}), XarrayDatasetOpener()
        )
        .diagnostics[0]
        .code
        == "invalid-open-hints"
    )


def test_xoptions_validated_and_candidate_scoping():
    resource = _resource(
        link=Link(href="s3://bucket/data", options={"sep": ";", "key": "SECRET"}),
        open_hints={"pandas": {"encoding": "utf-8"}},
    )
    candidate = JobResultContext(config=ClientConfig()).for_opener(
        resource, PandasDataFrameOpener()
    )
    assert candidate.options == {"sep": ";", "encoding": "utf-8"}
    assert len(candidate.diagnostics) == 1
    assert "SECRET" not in repr(candidate)


@pytest.mark.asyncio
async def test_provider_only_at_read_time_and_explicit_credentials_are_atomic():
    provider = AsyncMock()
    provider.resolve.return_value = {
        "key": "provider-key",
        "secret": "provider-secret",
        "token": "provider-token",
        "client_kwargs": {"region_name": "eu"},
    }

    class Config(ClientConfig):
        job_result_access_provider = provider

    resource = _resource()
    candidate = JobResultContext(
        config=Config(),
        options={
            "chunks": "auto",
            "backend_kwargs": {"consolidated": True},
            "storage_options": {"anon": False},
        },
    ).for_opener(resource, XarrayDatasetOpener())
    provider.resolve.assert_not_called()
    options = await candidate.reader_options(resource, storage_in_backend=True)
    assert options["backend_kwargs"]["consolidated"] is True
    assert options["backend_kwargs"]["storage_options"]["key"] == "provider-key"
    assert "storage_options" not in options
    provider.resolve.assert_awaited_once_with(resource)
    provider.reset_mock()

    class WithOldCredentials(Config):
        @classmethod
        def get_job_result_opener_options(cls, resource, opener_id):
            return {
                "storage_options": {
                    "key": "old",
                    "secret": "old-secret",
                    "token": "old-token",
                    "anon": False,
                }
            }

    candidate = JobResultContext(
        config=WithOldCredentials(),
        options={"storage_options": {"key": "new", "secret": "new-secret"}},
    ).for_opener(resource, XarrayDatasetOpener())
    options = await candidate.reader_options(resource, storage_in_backend=True)
    assert options["backend_kwargs"]["storage_options"] == {
        "key": "new",
        "secret": "new-secret",
        "anon": False,
    }
    provider.resolve.assert_not_called()
    assert (
        "new-secret" not in repr(candidate)
        and "provider-secret" not in resource.model_dump_json()
    )


@pytest.mark.parametrize(
    "hint",
    [
        {"storage_options": {"key": "SECRET"}},
        {"storage_options": {"endpoint_url": "https://evil.test"}},
        {"backend_kwargs": {"unknown": True}},
        {"backend_kwargs": {"storage_options": {"secret": "SECRET"}}},
        {"backend_kwargs": {"group": "valid", "consolidated": "wrong"}},
    ],
)
def test_unsupported_mapping_hints_are_not_forwarded(hint):
    candidate = JobResultContext(config=ClientConfig()).for_opener(
        _resource(open_hints={"xarray": hint}), XarrayDatasetOpener()
    )
    assert len(candidate.diagnostics) == 1
    assert candidate.options == {"engine": "zarr"}


@pytest.mark.asyncio
async def test_storage_alias_obeys_layer_precedence_and_nonsecret_inspection():
    class Config(ClientConfig):
        @classmethod
        def get_job_result_opener_options(cls, resource, opener_id):
            return {
                "backend_kwargs": {
                    "storage_options": {
                        "key": "old",
                        "secret": "old-secret",
                        "token": "old-token",
                        "anon": False,
                    }
                },
                "drop_variables": ["old"],
            }

    context = JobResultContext(
        config=Config(),
        options={
            "storage_options": {"key": "new", "secret": "new-secret"},
            "drop_variables": ["new"],
            "headers": {"Authorization": "SECRET"},
        },
    )
    candidate = context.for_opener(_resource(), XarrayDatasetOpener())
    assert (await candidate.reader_options(_resource(), storage_in_backend=True))[
        "backend_kwargs"
    ]["storage_options"] == {"key": "new", "secret": "new-secret", "anon": False}
    inspected = candidate.non_secret_options
    assert inspected == {
        "engine": "zarr",
        "drop_variables": ["new"],
        "backend_kwargs": {"storage_options": {"anon": False}},
    }
    assert "SECRET" not in str(inspected) and "new-secret" not in str(inspected)
    inspected["drop_variables"].append("independent")
    assert candidate.options["drop_variables"] == ["new"]
    cleared = JobResultContext(
        config=Config(), options={"backend_kwargs": None}
    ).for_opener(_resource(), XarrayDatasetOpener())
    assert cleared.options["backend_kwargs"] is None


def test_media_override_controls_defaults_and_link_parameters_remain_portable():
    resource = _resource(media_type="text/plain")
    candidate = JobResultContext(
        config=ClientConfig(), media_type="Application/Zarr; version=2"
    ).for_opener(resource, XarrayDatasetOpener())
    assert candidate.options == {"engine": "zarr"}
    assert resource.media_type == "text/plain"
    assert (
        JobResultContext(config=ClientConfig()).media_type_for(resource) == "text/plain"
    )


def test_scoped_hints_merge_with_validated_link_hints():
    resource = _resource(
        link=Link(
            href="s3://bucket/data",
            options={
                "backend_kwargs": {
                    "consolidated": True,
                    "storage_options": {"anon": True},
                }
            },
        ),
        open_hints={"xarray": {"backend_kwargs": {"group": "nested"}}},
    )
    candidate = JobResultContext(config=ClientConfig()).for_opener(
        resource, XarrayDatasetOpener()
    )
    assert candidate.options["backend_kwargs"] == {
        "consolidated": True,
        "group": "nested",
        "storage_options": {"anon": True},
    }
    assert not candidate.diagnostics


@pytest.mark.asyncio
async def test_same_context_shares_services_across_discovery_and_opening():
    fetch = AsyncMock(
        return_value=MetadataResponse(
            b'{"type":"Feature","stac_version":"1.1.0","id":"item","geometry":null,"properties":{},"links":[],"assets":{"data":{"href":"s3://asset-store/data","type":"application/zarr"}}}',
            "https://metadata.test/item.json",
        )
    )
    provider = AsyncMock()
    provider.resolve.return_value = {"key": "ACCESS_KEY", "secret": "SECRET"}

    class Config(ClientConfig):
        job_result_access_provider = provider

    loader = MetadataLoader(fetch, DiscoveryLimits(max_requests=1))
    source = Link(href="https://metadata.test/item.json", type="application/geo+json")
    context = JobResultContext(
        "dataset",
        source,
        config=Config(),
        loader=loader,
        data_type=xr.Dataset,
        options={"chunks": "auto"},
    )
    listing = await resolve_job_result(context, StacResolver)
    selected = listing.select(key="data")
    assert context.loader is loader and context.limits is loader.limits
    assert context.value is source and selected.media_type == "application/zarr"
    candidate = context.for_opener(selected, XarrayDatasetOpener())
    assert candidate.loader is loader and candidate.config is context.config
    assert candidate.output_name == "dataset" and candidate.value is source
    assert candidate.options == {"engine": "zarr", "chunks": "auto"}
    assert context.options == {"chunks": "auto"}
    assert await XarrayDatasetOpener().accept(selected, context=candidate)
    provider.resolve.assert_not_called()
    with patch("xarray.open_dataset", return_value="opened") as read:
        assert (
            await open_job_result(selected, XarrayDatasetOpener, context=context)
            == "opened"
        )
    read.assert_called_once_with(
        "s3://asset-store/data",
        engine="zarr",
        chunks="auto",
        backend_kwargs={"storage_options": {"key": "ACCESS_KEY", "secret": "SECRET"}},
    )
    fetch.assert_awaited_once()
    provider.resolve.assert_awaited_once_with(selected)
    assert "SECRET" not in selected.model_dump_json() and "SECRET" not in repr(context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "dispatch",
        "value-accept",
        "value-resolve",
        "stac-accept",
        "stac-resolve",
        "composed-accept",
        "composed-resolve",
        "transform",
    ],
)
@pytest.mark.parametrize("missing", ["name", "value"])
async def test_discovery_requires_source_inputs_before_io(operation, missing):
    fetch = AsyncMock()
    context = JobResultContext(
        output_name="x" if missing == "value" else "",
        config=ClientConfig(),
        loader=MetadataLoader(fetch),
    )
    composed = ComposedJobResultResolver(ValueResolver(), ())
    folder = FolderResourceTransformer(entries=(), matches=lambda resource, ctx: True)
    calls = {
        "dispatch": lambda: resolve_job_result(context, ValueResolver),
        "value-accept": lambda: ValueResolver().accept(context),
        "value-resolve": lambda: ValueResolver().resolve(context),
        "stac-accept": lambda: StacResolver().accept(context),
        "stac-resolve": lambda: StacResolver().resolve(context),
        "composed-accept": lambda: composed.accept(context),
        "composed-resolve": lambda: composed.resolve(context),
        "transform": lambda: folder.transform(_resource(), context),
    }
    with pytest.raises(ValueError, match=f"output {missing} is required for discovery"):
        await calls[operation]()
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_standalone_context_needs_no_client_and_fields_are_frozen():
    context = JobResultContext("x", None, options={"sep": ";"})
    resource = (await ValueResolver().resolve(context))[0]
    assert resource.has_value and resource.value is None
    selected = _resource(
        media_type="text/csv", open_hints={"pandas": {"encoding": "utf-8"}}
    )
    candidate = context.for_opener(selected, PandasDataFrameOpener())
    assert candidate.config is None
    assert await candidate.reader_options(selected) == {"sep": ";", "encoding": "utf-8"}
    with pytest.raises(FrozenInstanceError):
        context.output_name = "changed"
    with pytest.raises(ValueError, match="output name or client configuration"):
        JobResultContext()


def _resource(**changes):
    return JobResultResource(
        **(
            {
                "id": "r",
                "output_name": "x",
                "kind": "asset",
                "link": Link(href="s3://bucket/data"),
                "media_type": "application/zarr",
            }
            | changes
        )
    )
