import asyncio
import gc
import json
import os
import threading
from unittest.mock import patch

import httpx2
import pystac
import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.opener import JobResultOpenContext, JobResultOpenError
from cuiman.api.opener.impl import StacJobResultOpener
from cuiman.api.opener.impl._paths import _local_path
from cuiman.api.opener.opener import open_job_result
from cuiman.api.transport import TransportArgs
from cuiman.api.transport.httpx2 import Httpx2Transport
from gavicore.models import JobResults, Link


def document():
    return {
        "type": "Catalog",
        "stac_version": "1.1.0",
        "id": "catalog",
        "description": "test",
        "links": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("file_uri", [False, True])
async def test_default_pystac_reads_local_metadata_with_spaces(tmp_path, file_uri):
    path = tmp_path / "metadata with spaces.json"
    path.write_text(json.dumps(document()), encoding="utf-8")
    href = path.as_uri() if file_uri else str(path)
    ctx = JobResultOpenContext(
        config=ClientConfig(), value=Link(href=href, type="application/json")
    )
    result = await open_job_result(ctx, StacJobResultOpener)
    assert isinstance(result, pystac.Catalog) and result.id == "catalog"
    assert _local_path(result.get_self_href()) == path
    assert isinstance(result._stac_io, pystac.stac_io.DefaultStacIO)


@pytest.mark.asyncio
async def test_initial_read_is_off_thread_and_cancellation_propagates():
    started = threading.Event()
    release = threading.Event()
    thread_ids = []

    def read(source):
        thread_ids.append(threading.get_ident())
        started.set()
        release.wait(2)
        return document()

    ctx = JobResultOpenContext(
        config=ClientConfig(), value=Link(href="https://data.test/catalog.json")
    )
    with patch.object(pystac.stac_io.DefaultStacIO, "read_json", side_effect=read):
        task = asyncio.create_task(open_job_result(ctx, StacJobResultOpener))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            assert len(thread_ids) == 1 and thread_ids[0] != threading.get_ident()
            assert not task.done()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()


@pytest.mark.asyncio
async def test_read_failure_is_sanitized():
    ctx = JobResultOpenContext(
        config=ClientConfig(),
        value=Link(href="https://data.test/catalog.json?secret=token"),
    )
    with patch.object(
        pystac.stac_io.DefaultStacIO, "read_json", side_effect=OSError("secret=token")
    ):
        with pytest.raises(JobResultOpenError, match="OSError") as failure:
            await open_job_result(ctx, StacJobResultOpener)
    assert "secret" not in str(failure.value)


def test_local_path_conversion(tmp_path):
    path = tmp_path / "file with spaces.json"
    assert _local_path(path.as_uri()) == path
    assert _local_path(str(path)) == path
    assert _local_path("file://localhost" + path.as_uri()[7:]) == path
    if os.name == "nt":
        assert str(_local_path("file://server/share/item.json")).startswith(
            "\\\\server"
        )
    with patch("cuiman.api.opener.impl._paths.os.name", "posix"):
        with pytest.raises(JobResultOpenError, match="Remote file"):
            _local_path("file://server/share/item.json")
    with pytest.raises(JobResultOpenError, match="scheme"):
        _local_path("s3://bucket/item.json")


def test_native_io_factory_is_runtime_only():
    class Config(ClientConfig):
        stac_io_factory = staticmethod(lambda config: pystac.StacIO.default())

    assert "stac_io_factory" not in Config().to_file_dict()


def test_transport_defaults_and_job_context_source_facts():
    from tests.helpers import MockTransport

    from cuiman import Client
    from cuiman.api.jobs import JobOptions, _new_open_context
    from cuiman.api.transport import AsyncTransport, Transport
    from gavicore.models import JobInfo, JobStatus

    transport = MockTransport()
    assert Transport.get_response_href(transport, None) is None
    assert AsyncTransport.get_response_href(transport, None) is None
    client = Client(
        api_url="https://api.test", auth={"auth_type": "none"}, _transport=transport
    )
    try:
        with patch.object(
            transport,
            "get_response_href",
            return_value="https://api.test/effective.json",
        ):
            ctx = _new_open_context(
                client,
                JobInfo(jobID="a", status=JobStatus.successful),
                JobResults(root={"a": 1}),
                JobOptions(),
                None,
            )
        assert ctx.document_href == "https://api.test/effective.json"
    finally:
        client.close()


def test_transport_retains_effective_uri_per_result_and_releases_sources():
    transport = Httpx2Transport(api_url="https://api.test")

    def handle(request):
        return httpx2.Response(200, json={"item": 1})

    transport.sync_httpx2 = httpx2.Client(transport=httpx2.MockTransport(handle))
    first = transport.call(
        TransportArgs(path="/first", return_types={"200": JobResults})
    )
    second = transport.call(
        TransportArgs(path="/second", return_types={"200": JobResults})
    )
    assert transport.get_response_href(first) == "https://api.test/first"
    assert transport.get_response_href(second) == "https://api.test/second"
    assert transport.get_response_href(JobResults(root={"item": 1})) is None
    del first
    gc.collect()
    assert len(transport._result_sources) == 1
    transport.sync_httpx2.close()
