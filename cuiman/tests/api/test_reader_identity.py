"""Reader identities, explicit dispatch, option policies."""

from unittest.mock import AsyncMock, Mock, patch

import pystac
import pytest

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api import reader
from cuiman.api.reader import JobResultReadContext, JobResultReadError
from cuiman.api.reader.impl import (
    StacJobResultReader,
    XarrayDatasetReader,
    compose_stac_reader,
)
from cuiman.api.reader.reader import read_job_result
from gavicore.models.core import JobInfo, JobResults, JobStatus


class ContextReader(reader.JobResultReader):
    """Return the execution context to expose dispatch decisions."""

    reader_id = "context"

    async def accept_job_result(self, ctx):
        return True

    async def read_job_result(self, ctx):
        return ctx


@pytest.mark.parametrize("identity", [None, "", " ", 1])
def test_invalid_identity_rejected(identity):
    class InvalidReader(ContextReader):
        reader_id = identity

    with pytest.raises(ValueError, match="explicitly declare a non-empty reader_id"):
        reader.JobResultReaderRegistry().register(InvalidReader)


def test_identity_must_be_declared_and_unique():
    class InheritedReader(ContextReader):
        pass

    class DuplicateReader(ContextReader):
        reader_id = "context"

    registry = reader.JobResultReaderRegistry()
    registry.register(ContextReader)
    with pytest.raises(ValueError, match="explicitly declare"):
        registry.register(InheritedReader)
    with pytest.raises(ValueError, match="Duplicate.*context"):
        registry.register(DuplicateReader)
    assert registry.reader_types == (ContextReader,)
    registry.register(ContextReader)
    assert registry.reader_types == (ContextReader,)


@pytest.mark.asyncio
@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("target_kind", ["job", "asset"])
@pytest.mark.parametrize("identity", ["context", "unknown"])
async def test_clients_select_explicit_reader(client_type, target_kind, identity):
    class PreferredReader(ContextReader):
        reader_id = "preferred"

        async def read_job_result(self, ctx):
            pytest.fail("An explicit reader must bypass default precedence")

    class Config(ClientConfig):
        extra_job_result_readers = (ContextReader, PreferredReader)

    client = client_type(
        config_type=Config, api_url="https://example.test", auth={"auth_type": "none"}
    )
    method_mock = AsyncMock if client_type is AsyncClient else Mock
    target = (
        "job" if target_kind == "job" else pystac.Asset("https://data.test/file.csv")
    )
    try:
        with (
            patch.object(
                client,
                "get_job",
                method_mock(
                    return_value=JobInfo(jobID="job", status=JobStatus.successful)
                ),
            ),
            patch.object(
                client,
                "get_job_results",
                method_mock(return_value=JobResults(root={"result": 42})),
            ),
        ):

            async def call():
                result = client.read_job_result(target, reader_id=identity, custom=True)
                return await result if client_type is AsyncClient else result

            if identity == "unknown":
                with pytest.raises(
                    JobResultReadError, match="Unknown job result reader.*unknown"
                ):
                    await call()
            else:
                ctx = await call()
                assert ctx.reader_id == identity
                assert ctx.options == {"custom": True}
    finally:
        if client_type is AsyncClient:
            await client.close()
        else:
            client.close()


@pytest.mark.asyncio
async def test_selected_reader_rejection_does_not_fall_back():
    class RejectingReader(ContextReader):
        reader_id = "rejecting"

        async def accept_job_result(self, ctx):
            return False

    ctx = JobResultReadContext(config=ClientConfig(), value=42, reader_id="rejecting")
    with pytest.raises(JobResultReadError, match="No job result reader found"):
        await read_job_result(ctx, ContextReader, RejectingReader)


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_access", [False, True])
async def test_derived_reader_inherits_policy_with_own_identity(explicit_access):
    class DerivedReader(XarrayDatasetReader):
        reader_id = "project-dataset"

        async def read_job_result(self, ctx):
            return ctx

    class Config(ClientConfig):
        asset_reader_options = Mock(
            return_value={"storage_options": {"anon": True}} if explicit_access else {}
        )
        asset_access_provider = Mock(return_value={"anon": True})

    ctx = JobResultReadContext(
        config=Config(),
        value=pystac.Asset("s3://bucket/data.zarr", media_type="application/zarr"),
        location="s3://bucket/data.zarr",
        _media_type="application/zarr",
        reader_id="project-dataset",
    )
    registry = reader.JobResultReaderRegistry.create_default()
    registry.register(DerivedReader)
    actual = await read_job_result(ctx, *registry.reader_types)
    assert actual.options == {
        "engine": "zarr",
        "backend_kwargs": {"storage_options": {"anon": True}},
    }
    assert Config.asset_reader_options.call_args.args[1] == "project-dataset"
    if explicit_access:
        Config.asset_access_provider.assert_not_called()
    else:
        assert Config.asset_access_provider.call_args.args[1] == "project-dataset"
    assert ctx.options == {}


def test_composed_reader_identity_is_explicit_and_unique():
    async def transform(value, ctx):
        return value

    registry = reader.JobResultReaderRegistry.create_default()
    for identity in ["project-stac", "other-stac"]:
        composed = compose_stac_reader(
            StacJobResultReader, reader_id=identity, transformers=(transform,)
        )
        registry.register(composed)
        assert composed.reader_id == identity
