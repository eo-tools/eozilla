"""Bound default metadata transport reads and cross-operation cache reuse."""

import asyncio
from unittest.mock import AsyncMock

import httpx2
import pytest

from cuiman.api import metadata
from cuiman.api.metadata import (
    DiscoveryError,
    DiscoveryLimits,
    MetadataLoader,
    MetadataResponse,
    fetch_metadata,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["uri", "path", "localhost"])
async def test_local_metadata_exact_byte_bound_and_effective_base(tmp_path, location):
    path = tmp_path / "metadata with spaces.json"
    content = b'{"features": []}'
    path.write_bytes(content)
    href = str(path) if location == "path" else path.as_uri()
    if location == "localhost":
        href = href.replace("file:///", "file://localhost/")
    response = await fetch_metadata(href, max_bytes=len(content), timeout=1)
    assert response == MetadataResponse(content, path.as_uri())
    with pytest.raises(DiscoveryError) as error:
        await fetch_metadata(href, max_bytes=len(content) - 1, timeout=1)
    assert error.value.code == "byte-limit" and error.value.partial


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "href", ["s3://bucket/item.json", "file://remote/item.json", "relative.json"]
)
async def test_other_locations_need_application_fetcher(href):
    with pytest.raises(DiscoveryError, match="configured fetcher"):
        await fetch_metadata(href, max_bytes=100, timeout=1)


@pytest.mark.asyncio
async def test_http_redirect_base_content_type_and_no_authorization(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == "/original":
            return httpx2.Response(
                302, headers={"location": "https://redirect.test/item.json"}
            )
        return httpx2.Response(
            200,
            content=b'{"id": "item"}',
            headers={"content-type": "application/geo+json; charset=utf-8"},
        )

    factory = httpx2.AsyncClient
    monkeypatch.setattr(
        metadata.httpx2,
        "AsyncClient",
        lambda **kwargs: factory(transport=httpx2.MockTransport(respond), **kwargs),
    )
    result = await fetch_metadata(
        "https://source.test/original", max_bytes=100, timeout=1
    )
    assert result.url == "https://redirect.test/item.json"
    assert result.media_type == "application/geo+json; charset=utf-8"
    assert len(requests) == 2
    assert all("authorization" not in request.headers for request in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, content, expected",
    [(200, b"x" * 101, DiscoveryError), (403, b"denied", httpx2.HTTPStatusError)],
)
async def test_http_stops_on_byte_bound_or_status(
    monkeypatch, status, content, expected
):
    factory = httpx2.AsyncClient
    monkeypatch.setattr(
        metadata.httpx2,
        "AsyncClient",
        lambda **kwargs: factory(
            transport=httpx2.MockTransport(
                lambda request: httpx2.Response(status, content=content)
            ),
            **kwargs,
        ),
    )
    with pytest.raises(expected):
        await fetch_metadata("https://source.test/item.json", max_bytes=100, timeout=1)


@pytest.mark.asyncio
async def test_local_timeout_and_cancellation(monkeypatch):
    async def slow(*args):
        await asyncio.sleep(10)

    monkeypatch.setattr(metadata.asyncio, "to_thread", slow)
    with pytest.raises(TimeoutError):
        await fetch_metadata("file:///C:/item.json", max_bytes=100, timeout=0.001)
    task = asyncio.create_task(
        fetch_metadata("file:///C:/item.json", max_bytes=100, timeout=10)
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_operation_cache_is_independent_bounded_and_has_new_budget():
    fetch = AsyncMock(
        return_value=MetadataResponse(b'{"items": []}', "https://source.test/item.json")
    )
    loader = MetadataLoader(fetch, DiscoveryLimits(max_requests=1))
    await loader.load("first")
    fresh = loader.for_operation()
    assert fresh.request_count == 0 and fresh._lock is not loader._lock
    doc = await fresh.load("first")
    doc.value["items"].append(1)
    assert (await loader.load("first")).value["items"] == []
    await fresh.load("second")
    next_operation = fresh.for_operation()
    assert list(next_operation._cache) == ["second"]
    await next_operation.load("first")
    assert fetch.await_count == 3


@pytest.mark.asyncio
async def test_cached_failures_are_copied_and_refresh_retries():
    fetch = AsyncMock(side_effect=DiscoveryError("invalid", "safe", partial=True))
    loader = MetadataLoader(fetch)
    with pytest.raises(DiscoveryError) as first:
        await loader.load("url")
    fresh = loader.for_operation()
    with pytest.raises(DiscoveryError) as second:
        await fresh.load("url")
    assert first.value is not second.value
    assert second.value.code == "invalid" and second.value.partial
    assert fresh.request_count == 0
    fresh.clear()
    with pytest.raises(DiscoveryError):
        await fresh.load("url")
    assert fetch.await_count == 2
