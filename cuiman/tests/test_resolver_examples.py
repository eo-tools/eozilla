"""Run the discovery guide and notebook using real test-process products."""

import ast
import html
import inspect
import json
import re
import runpy
import sys
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pandas as pd
import pytest
from markdown import markdown

from cuiman.api.opener import JobResultStatusError
from cuiman.api.resolver import DiscoveryError, MetadataLoader
from examples.guides.cuiman import resolvers
from gavicore.models import JobInfo, JobResults
from procodile import Job
from wraptile.services.local.testing import service

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def resolver_client(monkeypatch, tmp_path):
    """Replace HTTP calls with actual local process executions and serialized results."""
    client = resolvers.create_client(tmp_path / "client-config.yaml")
    jobs = {}

    async def execute(process_id, request):
        job = Job.create(service.process_registry.get(process_id), request)
        results = job.run()
        assert job.job_info.status.value == "successful"
        jobs[job.job_info.jobID] = (job.job_info, results)
        return JobInfo(jobID=job.job_info.jobID, status="accepted")

    monkeypatch.setattr(
        client,
        "get_process",
        AsyncMock(
            side_effect=lambda process_id: (
                service.process_registry.get(process_id).description
            )
        ),
    )
    monkeypatch.setattr(client, "execute_process", AsyncMock(side_effect=execute))
    monkeypatch.setattr(
        client, "get_job", AsyncMock(side_effect=lambda job_id: jobs[job_id][0])
    )
    monkeypatch.setattr(
        client,
        "get_job_results",
        AsyncMock(
            side_effect=lambda job_id: JobResults.model_validate_json(
                jobs[job_id][1].model_dump_json()
            )
        ),
    )
    monkeypatch.setattr(resolvers, "create_client", lambda config_path: client)
    return client


@pytest.mark.asyncio
async def test_complete_resolver_session_reads_real_products(
    resolver_client, monkeypatch
):
    registry = resolver_client.config.get_job_result_resolver_registry()
    original = registry.resolver_types
    reads = []
    open_resource = resolver_client.open_job_result

    async def capture(resource, **options):
        table = await open_resource(resource, **options)
        reads.append((resource, table))
        return table

    monkeypatch.setattr(resolver_client, "open_job_result", capture)
    await resolvers.example_session()
    assert resolver_client.execute_process.call_count == 2
    assert registry.resolver_types == original
    assert [r.key for r, _ in reads] == ["data", "observations", "data"]
    assert reads[0][0].id != reads[1][0].id
    pd.testing.assert_frame_equal(reads[0][1], reads[1][1])
    assert reads[2][1].to_dict("records") == [{"date": "2026-09-02", "ndvi": 0.75}]
    assert all(
        not Path(url2pathname(urlsplit(r.link.href).path)).exists() for r, _ in reads
    )
    with pytest.raises(RuntimeError, match="closed"):
        await open_resource(reads[0][0])


@pytest.mark.asyncio
async def test_session_restores_registration_and_closes_after_discovery_failure(
    resolver_client, monkeypatch
):
    registry = resolver_client.config.get_job_result_resolver_registry()
    original = registry.resolver_types
    discover = resolvers.discover_output
    calls = 0

    async def failing_discovery(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("discovery failed")
        return await discover(*args, **kwargs)

    monkeypatch.setattr(resolvers, "discover_output", failing_discovery)
    close = AsyncMock(wraps=resolver_client.close)
    monkeypatch.setattr(resolver_client, "close", close)
    with pytest.raises(RuntimeError, match="discovery failed"):
        await resolvers.example_session()
    assert registry.resolver_types == original
    close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "dismissed", "accepted"])
async def test_submit_does_not_retrieve_unfinished_or_failed_results(
    resolver_client, tmp_path, status
):
    resolver_client.execute_process.return_value = JobInfo(
        jobID="failed", status=status
    )
    resolver_client.execute_process.side_effect = None
    error = TimeoutError if status == "accepted" else JobResultStatusError
    try:
        with pytest.raises(error):
            await resolvers.submit_stac(
                resolver_client, "simulate_stac_item", tmp_path, timeout=0
            )
        resolver_client.get_job_results.assert_not_called()
    finally:
        await resolver_client.close()


@pytest.mark.asyncio
async def test_local_fetcher_bounds_reads_and_loader_reuses_documents(tmp_path):
    path = tmp_path / "metadata with spaces.json"
    content = b'{"type": "FeatureCollection", "features": []}'
    path.write_bytes(content)
    response = await resolvers.fetch_local_metadata(
        path.as_uri(), max_bytes=len(content), timeout=1
    )
    assert response.content == content
    assert response.url == path.as_uri()
    assert response.media_type == "application/geo+json"
    with pytest.raises(DiscoveryError, match="size limit") as error:
        await resolvers.fetch_local_metadata(
            path.as_uri(), max_bytes=len(content) - 1, timeout=1
        )
    assert error.value.partial
    loader = MetadataLoader(resolvers.fetch_local_metadata)
    first = await loader.load(path.as_uri())
    first.value["features"].append({"id": "changed"})
    assert (await loader.load(path.as_uri())).value["features"] == []
    assert loader.request_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "href", ["https://example.com/items.json", "file://remote/items.json"]
)
async def test_local_fetcher_rejects_nonlocal_targets(href):
    with pytest.raises(DiscoveryError, match="local file URL"):
        await resolvers.fetch_local_metadata(href, max_bytes=100, timeout=1)


@pytest.mark.asyncio
async def test_rendered_resolver_guide_runs_in_order(resolver_client, monkeypatch):
    monkeypatch.setattr("cuiman.AsyncClient", lambda **kwargs: resolver_client)
    source = (ROOT / "docs/cuiman/guides/resolvers.md").read_text(encoding="utf-8")
    rendered = markdown(
        source,
        extensions=["fenced_code", "pymdownx.snippets"],
        extension_configs={
            "pymdownx.snippets": {
                "base_path": str(ROOT),
                "check_paths": True,
                "dedent_subsections": True,
            }
        },
    )
    blocks = re.findall(
        r'<pre><code class="language-python">(.*?)</code></pre>', rendered, re.DOTALL
    )
    assert blocks
    namespace = {}
    try:
        for block in blocks:
            result = eval(  # noqa: S307
                compile(
                    html.unescape(block),
                    "resolvers.md",
                    "exec",
                    flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
                ),
                namespace,
            )
            if inspect.isawaitable(result):
                await result
        assert namespace["table"].to_dict("records") == [
            {"date": "2026-09-01", "ndvi": 0.75}
        ]
        assert namespace["loader"].request_count == 1
    finally:
        await resolver_client.close()
        if "output" in namespace:
            namespace["output"].cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("working_directory", [ROOT, ROOT / "notebooks"])
async def test_notebook_cells_execute_against_real_test_products(
    resolver_client, monkeypatch, working_directory
):
    monkeypatch.chdir(working_directory)
    notebook = json.loads(
        (ROOT / "notebooks/cuiman-job-result-resources.ipynb").read_text(
            encoding="utf-8"
        )
    )
    namespace = {}
    original_path = list(sys.path)
    try:
        for cell in notebook["cells"]:
            if cell["cell_type"] != "code":
                continue
            assert cell["execution_count"] is None and cell["outputs"] == []
            result = eval(  # noqa: S307
                compile(
                    "".join(cell["source"]),
                    cell["id"],
                    "exec",
                    flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
                ),
                namespace,
            )
            if inspect.isawaitable(result):
                await result
        assert namespace["second_table"].to_dict("records") == [
            {"date": "2026-09-02", "ndvi": 0.75}
        ]
        assert namespace["loader"].request_count == 1
        assert resolver_client.execute_process.call_count == 2
        assert not namespace["root"].exists()
    finally:
        sys.path[:] = original_path
        await resolver_client.close()
        if "output" in namespace:
            namespace["output"].cleanup()


def test_importing_resolver_example_does_not_construct_clients(monkeypatch):
    def fail(**kwargs):
        raise AssertionError("Unexpected client construction")

    monkeypatch.setattr("cuiman.AsyncClient", fail)
    runpy.run_path(resolvers.__file__)


def test_resolver_script_runs_complete_session(resolver_client, monkeypatch):
    monkeypatch.setattr("cuiman.AsyncClient", lambda **kwargs: resolver_client)
    runpy.run_path(resolvers.__file__, run_name="__main__")
    assert resolver_client.execute_process.call_count == 2
