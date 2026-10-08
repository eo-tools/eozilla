import asyncio
import json
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pystac
import pytest
import xarray as xr

from cuiman import AsyncClient, Client
from cuiman.api.config import ClientConfig
from cuiman.api.exceptions import ClientWarning
from cuiman.api.opener import JobResultOpenContext, JobResultOpenError, JobResultOpener
from cuiman.api.opener.impl import (
    PandasDataFrameOpener,
    StacJobResultOpener,
    XarrayDatasetOpener,
)
from cuiman.api.opener.impl._stac.reader import prepare_asset_reader
from cuiman.api.opener.opener import open_job_result

XARRAY = "https://stac-extensions.github.io/xarray-assets/v1.0.0/schema.json"
STORAGE1 = "https://stac-extensions.github.io/storage/v1.0.0/schema.json"
STORAGE2 = "https://stac-extensions.github.io/storage/v2.0.0/schema.json"


def context(
    fields=None,
    extensions=(),
    properties=None,
    options=None,
    config=None,
    href="s3://bucket/data.zarr",
    media="application/x-zarr",
    collection=False,
):
    asset = pystac.Asset(href, media_type=media, extra_fields=fields or {})
    if collection:
        owner = pystac.Collection(
            "collection",
            "test",
            pystac.Extent(
                pystac.SpatialExtent([[-180, -90, 180, 90]]),
                pystac.TemporalExtent(
                    [[datetime(2026, 1, 1, tzinfo=timezone.utc), None]]
                ),
            ),
            extra_fields=properties or {},
        )
    else:
        owner = pystac.Item(
            "item",
            None,
            None,
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            properties or {},
        )
    owner.stac_extensions = list(extensions)
    owner.add_asset("data", asset)
    return JobResultOpenContext(
        config=config or ClientConfig(),
        value=asset,
        location=href,
        _media_type=media,
        options=options or {},
    )


@pytest.mark.asyncio
async def test_precedence_aliases_sources_and_no_mutation():
    overrides = {
        "chunks": {"x": 8},
        "storage_options": {
            "client_kwargs": {"region_name": "client"},
            "config_kwargs": {"retries": {"max_attempts": 2}},
        },
    }

    class Config(ClientConfig):
        asset_reader_options = Mock(return_value=overrides)

    ctx = context(
        {
            "x-options": {"chunks": {"x": 2, "y": 4}, "consolidated": False},
            "xarray:open_kwargs": {"chunks": {"x": 3}, "consolidated": True},
            "xarray:storage_options": {
                "requester_pays": True,
                "client_kwargs": {"region_name": "producer"},
            },
        },
        [XARRAY],
        options={
            "chunks": None,
            "backend_kwargs": {
                "storage_options": {"client_kwargs": {"region_name": "caller"}}
            },
        },
        config=Config(),
    )
    original = deepcopy(ctx.value.owner.to_dict())
    options = deepcopy(ctx.options)
    prepared = await prepare_asset_reader(ctx, "xarray")
    assert prepared.options == {
        "engine": "zarr",
        "chunks": None,
        "backend_kwargs": {
            "consolidated": True,
            "storage_options": {
                "requester_pays": True,
                "client_kwargs": {"region_name": "caller"},
                "config_kwargs": {"retries": {"max_attempts": 2}},
            },
        },
    }
    assert ctx.option_sources["backend_kwargs.consolidated"] == "producer"
    assert (
        ctx.option_sources["backend_kwargs.storage_options.client_kwargs.region_name"]
        == "caller"
    )
    assert ctx.option_sources["engine"] == "reader-default"
    assert ctx.resolved_options == prepared.options
    assert ctx.value.owner.to_dict() == original and ctx.options == options
    prepared.options["backend_kwargs"]["storage_options"]["requester_pays"] = False
    assert (
        ctx.resolved_options["backend_kwargs"]["storage_options"]["requester_pays"]
        is True
    )
    assert overrides["chunks"] == {"x": 8}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "version,collection", [(STORAGE1, False), (STORAGE2, False), (STORAGE2, True)]
)
async def test_storage_versions_owned_s3_hints(version, collection):
    fields = (
        {"storage:region": "eu-west-1"}
        if version == STORAGE1
        else {"storage:refs": ["aws"]}
    )
    properties = (
        {"storage:platform": "AWS", "storage:requester_pays": True}
        if version == STORAGE1
        else {
            "storage:schemes": {
                "aws": {
                    "type": "aws-s3",
                    "platform": "https://{bucket}.s3.{region}.amazonaws.com",
                    "bucket": "bucket",
                    "region": "eu-west-1",
                    "requester_pays": True,
                }
            }
        }
    )
    ctx = context(fields, [version], properties, collection=collection)
    prepared = await prepare_asset_reader(ctx, "xarray")
    assert prepared.options["backend_kwargs"]["storage_options"] == {
        "client_kwargs": {"region_name": "eu-west-1"},
        "requester_pays": True,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_provider_at_authenticated_zarr_reader_boundary(asynchronous):
    seen = []

    def access(ctx, asset_reader_id):
        seen.append((ctx.value, ctx.location, asset_reader_id, deepcopy(ctx.options)))
        return {
            "key": "provider-key",
            "secret": "provider-secret",
            "token": "provider-token",
            "client_kwargs": {"endpoint_url": "https://trusted.test"},
        }

    class Config(ClientConfig):
        asset_access_provider = (
            AsyncMock(side_effect=access) if asynchronous else Mock(side_effect=access)
        )

    ctx = context(
        {"xarray:open_kwargs": {"consolidated": True}},
        [XARRAY],
        config=Config(),
        options={"chunks": "auto", "storage_options": {"requester_pays": True}},
    )
    original = deepcopy(ctx.value.owner.to_dict())
    expected = xr.Dataset({"value": ("x", [1, 2])})
    with patch("xarray.open_dataset", return_value=expected) as read:
        opener = XarrayDatasetOpener()
        assert await opener.accept_job_result(ctx)
        Config.asset_access_provider.assert_not_called()
        assert await open_job_result(ctx, XarrayDatasetOpener) is expected
    assert seen[0][:3] == (ctx.value, ctx.location, "xarray")
    assert "key" not in json.dumps(seen[0][3])
    read.assert_called_once_with(
        "s3://bucket/data.zarr",
        engine="zarr",
        chunks="auto",
        backend_kwargs={
            "consolidated": True,
            "storage_options": {
                "key": "provider-key",
                "secret": "provider-secret",
                "token": "provider-token",
                "client_kwargs": {"endpoint_url": "https://trusted.test"},
                "requester_pays": True,
            },
        },
    )
    assert "provider-token" not in repr(ctx.resolved_options)
    assert ctx.value.owner.to_dict() == original
    assert (
        not {"asset_reader_options", "asset_access_provider"}
        & Config().to_file_dict().keys()
    )


@pytest.mark.asyncio
async def test_caller_credentials_replace_client_and_skip_provider():
    class Config(ClientConfig):
        asset_reader_options = Mock(
            return_value={
                "backend_kwargs": {
                    "storage_options": {
                        "key": "old",
                        "secret": "old",
                        "token": "old-token",
                        "client_kwargs": {"region_name": "eu"},
                    }
                }
            }
        )
        asset_access_provider = Mock(side_effect=AssertionError("provider forbidden"))

    ctx = context(
        config=Config(),
        options={
            "storage_options": {
                "aws_access_key_id": "new",
                "aws_secret_access_key": "new-secret",
            }
        },
    )
    prepared = await prepare_asset_reader(ctx, "xarray")
    assert prepared.options["backend_kwargs"]["storage_options"] == {
        "key": "new",
        "secret": "new-secret",
        "client_kwargs": {"region_name": "eu"},
    }
    assert "new-secret" not in repr(ctx.resolved_options)
    Config.asset_access_provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        {"storage_options": None},
        {"backend_kwargs": None},
        {"backend_kwargs": {"storage_options": None}},
        {"storage_options": {"anon": True}},
        {
            "storage_options": {
                "client_kwargs": {
                    "aws_access_key_id": "key",
                    "aws_secret_access_key": "secret",
                    "aws_session_token": "token",
                }
            }
        },
    ],
)
async def test_explicit_access_and_clearing_skip_provider(options):
    class Config(ClientConfig):
        asset_access_provider = Mock(side_effect=AssertionError("provider forbidden"))

    prepared = await prepare_asset_reader(
        context(config=Config(), options=options), "xarray"
    )
    assert prepared.options["engine"] == "zarr"
    Config.asset_access_provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields,extensions",
    [
        (
            {
                "x-options": {
                    "engine": "evil",
                    "callback": "secret-token",
                    "chunks": False,
                }
            },
            [],
        ),
        ({"xarray:open_kwargs": {"chunks": "auto"}}, []),
        (
            {"xarray:open_kwargs": {"chunks": "auto"}},
            [XARRAY.replace("1.0.0", "9.0.0")],
        ),
        (
            {
                "xarray:open_kwargs": [],
                "xarray:storage_options": {
                    "key": "secret-token",
                    "client_kwargs": {"endpoint_url": "https://secret-token.test"},
                },
                "xarray:future": "secret-token",
            },
            [XARRAY],
        ),
        (
            {
                "x-options": {
                    "backend_kwargs": {"storage_options": {"secret": "secret-token"}}
                }
            },
            [],
        ),
        ({"storage:region": "secret-token"}, []),
    ],
)
async def test_invalid_hints_preserved_and_sanitized(fields, extensions):
    ctx = context(fields, extensions)
    original = deepcopy(ctx.value.to_dict())
    with pytest.warns(ClientWarning) as messages:
        prepared = await prepare_asset_reader(ctx, "xarray")
    assert "secret-token" not in " ".join(str(w.message) for w in messages)
    assert "secret-token" not in repr(prepared.options)
    assert ctx.value.to_dict() == original


@pytest.mark.asyncio
async def test_reader_rejection_and_metadata_do_not_acquire_access():
    class Config(ClientConfig):
        asset_access_provider = Mock(side_effect=AssertionError("provider forbidden"))
        asset_reader_options = Mock(side_effect=AssertionError("options forbidden"))

    ctx = context(config=Config())
    with pytest.raises(JobResultOpenError, match="No job result opener"):
        await open_job_result(ctx, PandasDataFrameOpener)
    metadata = {
        "type": "Catalog",
        "stac_version": "1.1.0",
        "id": "test",
        "description": "test",
        "links": [],
    }
    native = await open_job_result(
        JobResultOpenContext(config=Config(), value=metadata), StacJobResultOpener
    )
    assert isinstance(native, pystac.Catalog)
    Config.asset_access_provider.assert_not_called()
    Config.asset_reader_options.assert_not_called()


@pytest.mark.asyncio
async def test_candidate_isolation_and_safe_grouped_errors():
    class Mutates(JobResultOpener):
        async def accept_job_result(self, ctx):
            ctx.options["backend_kwargs"]["consolidated"] = "mutated"
            return True

        async def open_job_result(self, ctx):
            raise OSError("secret-token in signed URL")

    ctx = context(options={"backend_kwargs": {"consolidated": True}})
    with patch("xarray.open_dataset", return_value="opened") as read:
        assert await open_job_result(ctx, Mutates, XarrayDatasetOpener) == "opened"
    assert read.call_args.kwargs["backend_kwargs"]["consolidated"] is True
    assert ctx.options == {"backend_kwargs": {"consolidated": True}}
    with pytest.raises(JobResultOpenError) as error:
        await open_job_result(ctx, Mutates)
    assert "secret-token" not in str(error.value) + str(error.value.__cause__)
    assert "secret-token" not in str(error.value.__cause__.exceptions[0])


@pytest.mark.parametrize("asynchronous", [False, True])
def test_both_client_reader_hints_without_processing_calls(asynchronous):
    ctx = context(
        {"x-options": {"delimiter": ";", "header": None}},
        href="https://data.test/report.csv",
        media="text/csv",
    )
    client = AsyncClient() if asynchronous else Client()
    runner = asyncio.Runner()
    with (
        patch.object(
            client, "get_job", side_effect=AssertionError("job lookup forbidden")
        ),
        patch("pandas.read_csv", return_value=pd.DataFrame({"a": [1]})) as read,
    ):
        result = client.open_job_result(
            ctx.value, data_type=pd.DataFrame, delimiter=","
        )
        result = runner.run(result) if asynchronous else result
        assert result.a.tolist() == [1]
    read.assert_called_once_with(
        "https://data.test/report.csv", delimiter=",", header=None
    )
    if asynchronous:
        runner.run(client.close())
    else:
        client.close()
    runner.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "asset_reader_id,hints",
    [
        (
            "xarray",
            {
                "drop_variables": ["a"],
                "decode_cf": False,
                "backend_kwargs": {"consolidated": None},
            },
        ),
        (
            "pandas",
            {
                "header": 0,
                "usecols": ["a"],
                "encoding": "utf-8",
                "storage_options": {"client_kwargs": {"region_name": "eu-west-1"}},
            },
        ),
        ("geopandas", {"columns": ["geometry", "a"]}),
        ("image", {"storage_options": {"requester_pays": True}}),
    ],
)
async def test_supported_reader_hint_schemas(asset_reader_id, hints):
    ctx = context({"x-options": hints}, href="s3://bucket/data.csv", media="text/csv")
    prepared = await prepare_asset_reader(ctx, asset_reader_id)
    assert prepared.options and ctx.resolved_options


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields,extensions,properties",
    [
        ({"storage:refs": []}, [STORAGE2], {}),
        ({"storage:refs": ["a", "b"]}, [STORAGE2], {}),
        (
            {"storage:refs": ["aws"]},
            [STORAGE2],
            {
                "storage:schemes": {
                    "aws": {"type": "custom-s3", "platform": "https://evil.test"}
                }
            },
        ),
        (
            {"storage:region": 42, "storage:requester_pays": "yes"},
            [STORAGE1],
            {"storage:platform": "AWS"},
        ),
        ({"storage:region": "eu"}, [STORAGE1], {"storage:platform": "Azure"}),
        ({"x-options": {"storage_options": []}}, [], {}),
        (
            {"x-options": {"storage_options": {"client_kwargs": {"region_name": 42}}}},
            [],
            {},
        ),
    ],
)
async def test_invalid_storage_does_not_set_endpoint_or_credentials(
    fields, extensions, properties
):
    ctx = context(fields, extensions, properties)
    with pytest.warns(ClientWarning):
        prepared = await prepare_asset_reader(ctx, "xarray")
    assert not prepared.options.get("backend_kwargs", {}).get("storage_options")


@pytest.mark.asyncio
async def test_http_storage_hints_do_not_invoke_s3_access():
    class Config(ClientConfig):
        asset_access_provider = Mock(side_effect=AssertionError("S3 access forbidden"))

    ctx = context(
        {"storage:region": "eu"},
        [STORAGE1],
        config=Config(),
        href="https://data.test/data.zarr",
    )
    await prepare_asset_reader(ctx, "xarray")
    Config.asset_access_provider.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides,access,options",
    [
        ([], None, {}),
        ({}, [], {}),
        ({}, None, {"backend_kwargs": []}),
        ({}, None, {"storage_options": 7}),
    ],
)
async def test_invalid_trusted_hook_results_fail_safely(overrides, access, options):
    class Config(ClientConfig):
        asset_reader_options = Mock(return_value=overrides)
        asset_access_provider = Mock(return_value=access)

    ctx = context(config=Config(), options=options)
    with pytest.raises(JobResultOpenError, match="mapping"):
        await prepare_asset_reader(ctx, "xarray")


@pytest.mark.asyncio
async def test_ambient_access_and_summary_redaction():
    class Config(ClientConfig):
        asset_access_provider = Mock(return_value=None)

    ctx = context(
        config=Config(),
        options={
            "drop_variables": ["a", "b"],
            "callback": object(),
            "opaque_list": [object()],
            "endpoint_url": "https://host.test?secret=token",
        },
    )
    prepared = await prepare_asset_reader(ctx, "xarray")
    Config.asset_access_provider.assert_called_once()
    assert prepared.options["endpoint_url"].endswith("secret=token")
    assert ctx.resolved_options == {"engine": "zarr", "drop_variables": ["a", "b"]}


@pytest.mark.asyncio
async def test_access_failure_and_cancellation():
    class Config(ClientConfig):
        asset_access_provider = AsyncMock(side_effect=OSError("secret-token"))

    ctx = context(config=Config())
    with patch("xarray.open_dataset", side_effect=AssertionError("reader forbidden")):
        with pytest.raises(JobResultOpenError) as error:
            await open_job_result(ctx, XarrayDatasetOpener)
    assert "secret-token" not in str(error.value.__cause__.exceptions[0])
    Config.asset_access_provider.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await open_job_result(ctx, XarrayDatasetOpener)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_s3_access_uses_receiving_client_for_foreign_asset(asynchronous):
    calls = []

    def access(ctx, asset_reader_id):
        assert ctx.location == "s3://bucket/data.zarr" and asset_reader_id == "xarray"
        calls.append(ctx.config.api_url)
        return {"key": "receiving-key", "secret": "receiving-secret"}

    class Config(ClientConfig):
        asset_access_provider = staticmethod(access)

    ctx = context()
    client = (AsyncClient if asynchronous else Client)(
        config=Config(api_url="https://receiving.test")
    )
    runner = asyncio.Runner()
    original = deepcopy(ctx.value.owner.to_dict())
    with patch("xarray.open_dataset", return_value=xr.Dataset()) as read:
        result = client.open_job_result(ctx.value, data_type=xr.Dataset)
        result = runner.run(result) if asynchronous else result
        assert isinstance(result, xr.Dataset)
    assert calls == [client.config.api_url]
    assert read.call_args.kwargs["backend_kwargs"]["storage_options"] == {
        "key": "receiving-key",
        "secret": "receiving-secret",
    }
    assert ctx.value.owner.to_dict() == original
    if asynchronous:
        runner.run(client.close())
    else:
        client.close()
    runner.close()


@pytest.mark.asyncio
async def test_aliases_replace_credentials_within_one_layer():
    ctx = context(
        options={
            "backend_kwargs": {
                "storage_options": {
                    "key": "old",
                    "secret": "old",
                    "token": "stale",
                    "client_kwargs": {"region_name": "eu"},
                }
            },
            "storage_options": {
                "aws_access_key_id": "new",
                "aws_secret_access_key": "new-secret",
            },
        }
    )
    prepared = await prepare_asset_reader(ctx, "xarray")
    assert prepared.options["backend_kwargs"]["storage_options"] == {
        "key": "new",
        "secret": "new-secret",
        "client_kwargs": {"region_name": "eu"},
    }


@pytest.mark.asyncio
async def test_non_csv_reader_rejects_csv_metadata_options():
    ctx = context(
        {"x-options": {"delimiter": ";"}},
        href="https://data.test/data.parquet",
        media="application/parquet",
    )
    with pytest.warns(ClientWarning):
        prepared = await prepare_asset_reader(ctx, "pandas")
    assert prepared.options == {}


@pytest.mark.asyncio
async def test_summaries_hide_signed_lists_malformed_urls_and_non_string_keys():
    ctx = context(
        options={
            "urls": ["https://host.test?token=secret"],
            "malformed": "https://[",
            "trusted_mapping": {17: "secret"},
        }
    )
    await prepare_asset_reader(ctx, "xarray")
    assert ctx.resolved_options == {"engine": "zarr", "trusted_mapping": {}}


@pytest.mark.asyncio
async def test_runtime_session_identity_is_retained_outside_metadata_and_summaries():
    class Session:
        def __deepcopy__(self, memo):
            raise AssertionError("session must not be copied")

    session = Session()
    ctx = context(
        options={"storage_options": {"session": session}, "runtime_tuple": ("a", ["b"])}
    )
    with patch("xarray.open_dataset", return_value=xr.Dataset()) as read:
        await open_job_result(ctx, XarrayDatasetOpener)
    assert (
        read.call_args.kwargs["backend_kwargs"]["storage_options"]["session"] is session
    )
    assert "session" not in repr(ctx.resolved_options)
    assert (
        read.call_args.kwargs["runtime_tuple"][1] is not ctx.options["runtime_tuple"][1]
    )
