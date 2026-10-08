import asyncio
import gc
import os
import threading
import time
from unittest.mock import patch

import httpx2
import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.opener import StacJobResultOpenError, StacMetadataIO
from cuiman.api.opener.metadata import _local_path, _origin
from cuiman.api.transport import TransportArgs
from cuiman.api.transport.httpx2 import Httpx2Transport
from gavicore.models import JobResults


@pytest.mark.parametrize(
    "limit,value",
    [
        ("max_bytes", 0),
        ("max_requests", 0),
        ("timeout", 0),
        ("timeout", float("inf")),
        ("timeout", float("nan")),
    ],
)
def test_invalid_limits(limit, value):
    with pytest.raises(ValueError):
        StacMetadataIO(**{limit: value})
    with pytest.raises(ValueError):
        ClientConfig(**{"stac_metadata_" + limit: value})


@pytest.mark.asyncio
async def test_file_reads_cache_limits_and_independent_operations(tmp_path):
    path = tmp_path / "file with spaces.json"
    path.write_text("hello", encoding="utf-8")
    reader = StacMetadataIO(max_bytes=5, max_requests=1)
    assert await reader.async_read_text_with_href(str(path)) == ("hello", path.as_uri())
    path.write_text("changed", encoding="utf-8")
    assert reader.read_text_with_href(path.as_uri())[0] == "hello"
    other = tmp_path / "other.json"
    other.write_text("ok", encoding="utf-8")
    with pytest.raises(StacJobResultOpenError, match="request limit"):
        reader.read_text_with_href(str(other))
    assert reader.new_operation().read_text_with_href(str(other))[0] == "ok"
    with pytest.raises(StacJobResultOpenError, match="byte limit"):
        await reader.new_operation().async_read_text_with_href(str(path))
    with pytest.raises(StacJobResultOpenError, match="byte limit"):
        reader.new_operation().read_text_with_href(str(path))
    with pytest.raises(StacJobResultOpenError, match="FileNotFoundError"):
        reader.new_operation().read_text_with_href(
            str(tmp_path / "missing-secret.json")
        )
    with pytest.raises(StacJobResultOpenError, match="FileNotFoundError") as failure:
        await reader.new_operation().async_read_text_with_href(
            str(tmp_path / "missing-secret.json")
        )
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_redirect_headers_budgets_cache_and_sanitized_errors(asynchronous):
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.host == "a.test":
            return httpx2.Response(
                302,
                headers={
                    "location": "https://b.test/result.json?signature=private",
                    "set-cookie": "auth=private; Domain=test; Path=/",
                },
            )
        return httpx2.Response(200, content=b"{}")

    reader = StacMetadataIO(
        max_requests=2,
        headers_by_origin={"https://a.test": {"Authorization": "Bearer secret"}},
        sync_transport_factory=lambda: httpx2.MockTransport(handle),
        async_transport_factory=lambda: httpx2.MockTransport(handle),
    )

    def read(policy, source):
        return (
            asyncio.run(policy.async_read_text_with_href(source))
            if asynchronous
            else policy.read_text_with_href(source)
        )

    text, effective = read(reader, "https://a.test/start.json")
    assert text == "{}" and effective == "https://b.test/result.json?signature=private"
    assert seen[0].headers["authorization"] == "Bearer secret"
    assert "authorization" not in seen[1].headers and "cookie" not in seen[1].headers
    assert read(reader, effective) == (text, effective)
    assert len(seen) == 2
    with pytest.raises(StacJobResultOpenError, match="request limit"):
        read(reader, "https://b.test/other.json")
    reader.max_requests = 1
    with pytest.raises(StacJobResultOpenError, match="request limit"):
        read(reader.new_operation(), "https://a.test/start.json")
    reader.max_requests = 2
    reader.max_bytes = 1
    with pytest.raises(StacJobResultOpenError, match="byte limit"):
        read(reader.new_operation(), "https://b.test/result.json")


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("mode", ["status", "unsupported", "invalid-utf8", "failure"])
def test_metadata_failure_sanitization(asynchronous, mode):
    def handle(request):
        if mode == "failure":
            raise RuntimeError("credential=private")
        if mode == "status":
            return httpx2.Response(403)
        if mode == "unsupported":
            return httpx2.Response(302, headers={"location": "file:///private.json"})
        return httpx2.Response(200, content=b"\xff")

    reader = StacMetadataIO(
        sync_transport_factory=lambda: httpx2.MockTransport(handle),
        async_transport_factory=lambda: httpx2.MockTransport(handle),
    )
    with pytest.raises(StacJobResultOpenError) as failure:
        if asynchronous:
            asyncio.run(
                reader.async_read_text_with_href("https://a.test/?secret=private")
            )
        else:
            reader.read_text_with_href("https://a.test/?secret=private")
    assert "private" not in str(failure.value) and "secret" not in str(failure.value)


class SlowStream(httpx2.AsyncByteStream):
    def __init__(self):
        self.closed = False
        self.started = asyncio.Event()

    async def __aiter__(self):
        self.started.set()
        await asyncio.sleep(10)
        yield b"{}"

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_stream_timeout_cancellation_and_cleanup(cancel):
    stream = SlowStream()
    reader = StacMetadataIO(
        timeout=0.02 if not cancel else 10,
        async_transport_factory=lambda: httpx2.MockTransport(
            lambda request: httpx2.Response(200, stream=stream)
        ),
    )
    task = asyncio.create_task(reader.async_read_text_with_href("https://a.test/a"))
    await stream.started.wait()
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else StacJobResultOpenError):
        await task
    assert stream.closed


@pytest.mark.asyncio
async def test_file_io_off_loop_and_cancellation():
    started = threading.Event()
    stopped = threading.Event()

    def read(source, stop):
        started.set()
        stop.wait(2)
        stopped.set()
        return "{}", "file:///result.json"

    reader = StacMetadataIO()
    with patch.object(reader, "_read_file", side_effect=read):
        task = asyncio.create_task(reader.async_read_text_with_href("unused"))
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(stopped.wait, 1)


def test_file_deadline_and_stop(tmp_path):
    path = tmp_path / "test.json"
    path.write_text("{}", encoding="utf-8")
    reader = StacMetadataIO()
    stop = threading.Event()
    stop.set()
    with pytest.raises(StacJobResultOpenError, match="cancelled"):
        reader._read_file(str(path), stop)
    with pytest.raises(StacJobResultOpenError, match="timed out"):
        reader._check_deadline(time.monotonic() - 1)
    with pytest.raises(StacJobResultOpenError, match="scheme"):
        reader.read_text_with_href("s3://bucket/item.json")
    assert _local_path("file://localhost" + path.as_uri()[7:]) == path
    with pytest.raises(StacJobResultOpenError, match="origin"):
        _origin("https://username:secret@host/")
    if os.name == "nt":
        assert str(_local_path("file://server/share/item.json")).startswith(
            "\\\\server"
        )
    with patch("cuiman.api.opener.metadata.os.name", "posix"):
        with pytest.raises(StacJobResultOpenError, match="Remote file"):
            _local_path("file://server/share/item.json")


def test_configured_limits_persist_and_factory_is_runtime_only():
    config = ClientConfig(
        stac_metadata_max_bytes=1024,
        stac_metadata_timeout=2,
        stac_metadata_max_requests=3,
    )
    saved = config.to_file_dict()
    restored = ClientConfig(**saved)
    reader = restored.create_stac_metadata_io()
    assert (reader.max_bytes, reader.timeout, reader.max_requests) == (1024, 2, 3)
    assert "stac_metadata_io_factory" not in saved


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
