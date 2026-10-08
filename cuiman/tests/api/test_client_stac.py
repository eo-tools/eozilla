from unittest.mock import Mock
from urllib.parse import urlsplit

import httpx2
import pystac
import pytest

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.transport.httpx2 import Httpx2Transport
from gavicore.models import ProcessRequest
from procodile import Job
from wraptile.services.local.testing import service


@pytest.mark.parametrize("inline", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_demo_job_opening_with_both_clients(
    inline, asynchronous, tmp_path, monkeypatch
):
    monkeypatch.setenv("EOZILLA_TESTING_STAC_DIR", str(tmp_path))
    monkeypatch.setenv("EOZILLA_TESTING_STAC_URL", "https://metadata.test/testing-stac")
    process = service.process_registry.get(
        "create_inline_stac" if inline else "create_linked_stac"
    )
    job = Job.create(process, ProcessRequest(inputs={"item_count": 2}))
    results = job.run()
    original = results.model_dump(mode="json")
    metadata_reads = []

    def handle_metadata(request):
        assert request.url.host == "metadata.test"
        assert "authorization" not in request.headers
        metadata_reads.append(str(request.url))
        relative = urlsplit(str(request.url)).path.removeprefix("/testing-stac/")
        return httpx2.Response(200, content=(tmp_path / relative).read_bytes())

    class Config(ClientConfig):
        @staticmethod
        def stac_io_factory(config):
            io = pystac.StacIO.default()
            io.read_json = Mock(
                side_effect=lambda href: handle_metadata(
                    httpx2.Request("GET", href)
                ).json()
            )
            return io

    def handle_api(request):
        if request.url.path == "/jobs/demo":
            return httpx2.Response(
                200,
                json={
                    "jobID": "demo",
                    "processID": process.description.id,
                    "status": "successful",
                },
            )
        if request.url.path == "/jobs/demo/results":
            # Simulate a redirected result response. The effective source is per response.
            return httpx2.Response(
                200,
                json=original,
                request=httpx2.Request(
                    "GET", "https://process.test/effective/results.json"
                ),
            )
        if request.url.path == f"/processes/{process.description.id}":
            return httpx2.Response(
                200, json=process.description.model_dump(mode="json", by_alias=True)
            )
        raise AssertionError(str(request.url))

    transport = Httpx2Transport(
        api_url="https://process.test",
        sync_httpx2=None
        if asynchronous
        else httpx2.Client(transport=httpx2.MockTransport(handle_api)),
        async_httpx2=httpx2.AsyncClient(transport=httpx2.MockTransport(handle_api))
        if asynchronous
        else None,
    )

    def validate(item, collection, raw):
        assert isinstance(item, pystac.Item)
        assert isinstance(collection, pystac.ItemCollection)
        assert [member.id for member in collection] == ["scene-1", "scene-2"]
        assert item.assets["data"].href.startswith(
            "https://metadata.test/testing-stac/"
        )
        assert collection[0].assets["data"].href == item.assets["data"].href
        assert collection[0].assets["data"].owner is collection[0]
        assert raw.model_dump(mode="json") == original
        assert results.model_dump(mode="json") == original
        assert len(metadata_reads) == (0 if inline else 2)

    if asynchronous:
        import asyncio

        async def run():
            underlying = transport.async_httpx2
            client = AsyncClient(
                api_url="https://process.test",
                auth={"auth_type": "none"},
                config_type=Config,
                _transport=transport,
            )
            try:
                item = await client.open_job_result(
                    "demo", output_name="item", data_type=pystac.Item
                )
                collection = await client.open_job_result(
                    "demo", output_name="item_collection"
                )
                raw = await client.get_job_results("demo")
                validate(item, collection, raw)
            finally:
                await client.close()
                await underlying.aclose()

        asyncio.run(run())
    else:
        underlying = transport.sync_httpx2
        client = Client(
            api_url="https://process.test",
            auth={"auth_type": "none"},
            config_type=Config,
            _transport=transport,
        )
        try:
            item = client.open_job_result(
                "demo", output_name="item", data_type=pystac.Item
            )
            collection = client.open_job_result("demo", output_name="item_collection")
            raw = client.get_job_results("demo")
            validate(item, collection, raw)
        finally:
            client.close()
            underlying.close()
