"""Read supplied results without rediscovering their producing job."""

from copy import deepcopy
from unittest.mock import Mock

import httpx2
import pandas as pd
import pystac
import pytest
import pytest_asyncio

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.reader import JobResultReader, JobResultReadError
from cuiman.api.transport.httpx2 import Httpx2Transport
from gavicore.models.core import JobResults, Link, QualifiedValue


async def read(client, *args, **kwargs):
    result = client.read_job_result(*args, **kwargs)
    return await result if isinstance(client, AsyncClient) else result


async def close(client):
    if isinstance(client, AsyncClient):
        await client.close()
    else:
        client.close()


@pytest.fixture(params=[Client, AsyncClient])
def client_type(request):
    return request.param


@pytest.fixture
def forbid_api(monkeypatch):
    calls = []

    def guard(client):
        for name in ("get_job", "get_job_results", "get_process", "_create_transport"):
            method = Mock(side_effect=AssertionError(f"Unexpected {name}"))
            monkeypatch.setattr(client, name, method)
            calls.append(method)

    yield guard
    for method in calls:
        method.assert_not_called()


@pytest.fixture
def contexts():
    return []


@pytest_asyncio.fixture
async def client(client_type, forbid_api, contexts):
    class SelectedReader(JobResultReader):
        reader_id = "selected"

        async def accept_job_result(self, ctx):
            return True

        async def read_job_result(self, ctx):
            contexts.append(ctx)
            return ctx.value

    class Config(ClientConfig):
        extra_job_result_readers = (SelectedReader,)

    instance = client_type(config_type=Config, api_url="https://unrelated.test/api")
    forbid_api(instance)
    try:
        yield instance
    finally:
        await close(instance)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outputs,output_name,selected_name",
    [
        ({"only": None}, None, "only"),
        ({"only": False}, None, "only"),
        ({"only": 0}, None, "only"),
        ({"only": ""}, None, "only"),
        ({"only": [1, None]}, None, "only"),
        ({"only": {"nested": [1]}}, None, "only"),
        ({"only": QualifiedValue(value=[2])}, None, "only"),
        ({"": 0, "other": 1}, "", ""),
        ({"return_value": 1, "null": None}, "null", "null"),
    ],
)
async def test_supplied_results_selection_and_copy(
    client, contexts, outputs, output_name, selected_name
):
    results = JobResults(root=outputs)
    original = results.model_dump(mode="json")
    # The existing keyword target call form also accepts results.
    value = await read(client, job_id_or_asset=results, output_name=output_name)
    assert value == results.root[selected_name]
    ctx = contexts[0]
    assert ctx.job_results is results
    assert ctx.job_id is None
    assert ctx.process_description is None
    assert ctx.output_name == selected_name
    assert ctx.document_href is None
    if isinstance(value, list):
        value.append(3)
    elif isinstance(value, dict):
        value["nested"].append(3)
    elif isinstance(value, QualifiedValue):
        value.value.append(3)
    assert results.model_dump(mode="json") == original


@pytest.mark.asyncio
async def test_supplied_results_preserve_reader_arguments(client, contexts):
    results = JobResults(root={"data": [1], "other": 2})
    options = {"nested": [3]}
    value = await read(
        client,
        results,
        "data",
        list,
        "application/custom",
        -1,
        -1,
        reader_id="selected",
        custom=options,
    )
    assert value == [1]
    ctx = contexts[0]
    assert ctx.data_type is list
    assert ctx.output_media_type == "application/custom"
    assert ctx.reader_id == "selected"
    assert ctx.options == {"custom": options}
    ctx.options["custom"]["nested"].append(4)
    assert options == {"nested": [3]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outputs,output_name,message",
    [
        (None, None, "contain no outputs"),
        ({}, None, "contain no outputs"),
        ({"data": None}, "missing", "'missing' does not exist"),
        ({"a": 1, "b": 2}, None, "Multiple job outputs"),
        ({"return_value": 1, "b": 2}, None, "Multiple job outputs"),
    ],
)
async def test_supplied_results_reject_invalid_selection(
    client, contexts, outputs, output_name, message
):
    with pytest.raises(JobResultReadError, match=message):
        await read(client, JobResults(root=outputs), output_name=output_name)
    assert contexts == []


@pytest.mark.asyncio
async def test_supplied_results_enforce_return_type(client):
    with pytest.raises(JobResultReadError, match="expected str"):
        await read(client, JobResults(root={"data": [1]}), data_type=str)


@pytest.mark.asyncio
async def test_closed_client_rejects_supplied_results(client, contexts):
    await close(client)
    with pytest.raises(RuntimeError, match="closed"):
        await read(client, JobResults(root={"data": 1}))
    assert contexts == []


@pytest.mark.asyncio
async def test_supplied_linked_csv_uses_builtin_reader(
    client_type, forbid_api, tmp_path
):
    path = tmp_path / "data.csv"
    path.write_text("value;label\n1;one\n2;two\n", encoding="utf-8")
    results = JobResults(root={"data": Link(href=path.as_uri())})
    original = results.model_dump(mode="json")
    client = client_type(api_url="https://unrelated.test/api")
    forbid_api(client)
    try:
        frame = await read(
            client,
            results,
            "data",
            pd.DataFrame,
            "text/csv",
            reader_id="pandas",
            sep=";",
        )
        assert frame.to_dict("list") == {"value": [1, 2], "label": ["one", "two"]}
        assert results.model_dump(mode="json") == original
    finally:
        await close(client)


def item(self_href=None):
    document = {
        "type": "Feature",
        "stac_version": "1.1.0",
        "id": "scene",
        "geometry": None,
        "properties": {"datetime": "2026-01-01T00:00:00Z"},
        "links": [],
        "assets": {"data": {"href": "data.csv", "type": "text/csv"}},
    }
    if self_href is not None:
        document["links"].append({"rel": "self", "href": self_href})
    return document


@pytest.mark.asyncio
@pytest.mark.parametrize("inline", [False, True])
@pytest.mark.parametrize("same_client", [False, True])
async def test_supplied_results_retain_redirect_base_without_refetch(
    client_type, forbid_api, inline, same_client
):
    requests = []
    body = {
        "item": item() if inline else {"href": "item.json", "type": "application/json"},
        "other": {"href": "never-read.json", "type": "application/json"},
    }

    def handle(request):
        requests.append(str(request.url))
        if request.url.path == "/jobs/job/results":
            return httpx2.Response(302, headers={"Location": "/effective/results.json"})
        if request.url.path == "/effective/results.json":
            return httpx2.Response(200, json=body)
        assert request.url.path == "/effective/item.json"
        return httpx2.Response(200, json=item())

    with httpx2.Client(
        transport=httpx2.MockTransport(handle), follow_redirects=True
    ) as http:

        class Config(ClientConfig):
            @staticmethod
            def stac_io_factory(config):
                io = pystac.StacIO.default()
                io.read_json = lambda href: http.get(href).json()
                return io

        transport = Httpx2Transport(api_url="https://source.test", sync_httpx2=http)
        # Use both client modes for result retrieval as well as subsequent reads.
        if client_type is AsyncClient:

            async def request(*args, **kwargs):
                return http.request(*args, **kwargs)

            transport.sync_httpx2 = None
            transport.async_request = request
        origin = client_type(
            config_type=Config, api_url="https://source.test", _transport=transport
        )
        receiver = origin
        try:
            results = origin.get_job_results("job")
            if client_type is AsyncClient:
                results = await results
            original = results.model_dump(mode="json")
            if not same_client:
                await close(origin)
                receiver = client_type(
                    config_type=Config, api_url="https://unrelated.test/api"
                )
                assert receiver._transport is None
            forbid_api(receiver)
            value = await read(receiver, results, "item", data_type=pystac.Item)
            assert value.assets["data"].href == "https://source.test/effective/data.csv"
            assert results.model_dump(mode="json") == original
            assert requests == [
                "https://source.test/jobs/job/results",
                "https://source.test/effective/results.json",
            ] + ([] if inline else ["https://source.test/effective/item.json"])
        finally:
            await close(receiver)
            await close(origin)


@pytest.mark.asyncio
@pytest.mark.parametrize("provenance", ["manual", "copy", "self"])
async def test_supplied_results_without_registered_base(
    client_type, forbid_api, provenance
):
    from cuiman.api.transport._result_sources import register_response_href

    results = JobResults(
        root={
            "item": item(
                "https://data.test/item.json" if provenance == "self" else None
            )
        }
    )
    if provenance == "copy":
        register_response_href(results, "https://origin.test/results.json")
        results = results.model_copy(deep=True)
    original = deepcopy(results.model_dump(mode="json"))
    client = client_type(api_url="https://unrelated.test/api")
    forbid_api(client)
    try:
        if provenance == "self":
            value = await read(client, results, data_type=pystac.Item)
            assert value.assets["data"].href == "https://data.test/data.csv"
        else:
            with pytest.raises(JobResultReadError, match="no containing document base"):
                await read(client, results, data_type=pystac.Item)
        assert results.model_dump(mode="json") == original
    finally:
        await close(client)
