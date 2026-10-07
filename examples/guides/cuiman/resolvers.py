"""Discover and open STAC results from the local testing service.

Run ``python -m examples.guides.cuiman.resolvers`` from the repository root with
``pixi run serve`` running in another terminal. The server and client must share
the filesystem. Imports do not connect, submit work, or register extensions.
"""

# --8<-- [start:imports]
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import url2pathname

import pandas as pd

from cuiman import AsyncClient, ClientConfig, JobResultContext
from cuiman.api.opener import JobResultStatusError
from cuiman.api.resolver import (
    ComposedJobResultResolver,
    DiscoveryError,
    FolderResourceTransformer,
    MetadataLoader,
    MetadataResponse,
    ResourceEntry,
    resolve_job_result,
)
from cuiman.api.resolver.impl import StacResolver
from cuiman.api.resources import JobResultResourceListing
from gavicore.models import JobResults, JobStatus, ProcessDescription, ProcessRequest

# --8<-- [end:imports]


# --8<-- [start:client]
class GuideConfig(ClientConfig):
    """Keep this example's temporary registrations separate from other clients."""


def create_client(config_path: Path) -> AsyncClient:
    """Select the testing service using a fresh profile inside the demo directory."""
    return AsyncClient(
        config_type=GuideConfig,
        config_path=str(config_path),
        api_url="http://127.0.0.1:8008",
        auth={"auth_type": "none"},
    )


# --8<-- [end:client]


# --8<-- [start:submit]
async def submit_stac(
    client: AsyncClient, process_id: str, output_dir: Path, *, timeout: float = 30
) -> tuple[str, JobResults, ProcessDescription]:
    """Submit one test process and retrieve its original outputs after completion.

    Both STAC test processes accept an output directory on the server. Retaining
    the job ID and process description lets discovery record their provenance.
    """
    process = await client.get_process(process_id)
    job = await client.execute_process(
        process_id, request=ProcessRequest(inputs={"output_dir": str(output_dir)})
    )
    deadline = asyncio.get_running_loop().time() + timeout
    while job.status in (JobStatus.accepted, JobStatus.running):
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"Job {job.jobID} did not finish within {timeout}s")
        await asyncio.sleep(0.1)
        job = await client.get_job(job.jobID)
    if job.status != JobStatus.successful:
        raise JobResultStatusError(job)
    return job.jobID, await client.get_job_results(job.jobID), process


# --8<-- [end:submit]


# --8<-- [start:discovery]
async def discover_output(
    client: AsyncClient,
    job_id: str,
    results: JobResults,
    process: ProcessDescription,
    *,
    output_name: str = "result",
    loader: MetadataLoader | None = None,
) -> JobResultResourceListing:
    """Adapt one completed output to the implemented developer discovery contract.

    Client listing methods are still pending. This guide helper supplies source
    facts and dispatches the receiving configuration's resolver classes directly.
    It does not alter the original results or open any Asset data.
    """
    context = JobResultContext(
        output_name=output_name,
        value=(results.root or {})[output_name],
        job_id=job_id,
        service_url=client.config.api_url,
        process_description=process,
        output_description=(process.outputs or {}).get(output_name),
        config=client.config,
        loader=loader,
    )
    registry = client.config.get_job_result_resolver_registry()
    return await resolve_job_result(context, *registry.resolver_types)


# --8<-- [end:discovery]


# --8<-- [start:fetcher]
async def fetch_local_metadata(
    href: str, *, max_bytes: int, timeout: float
) -> MetadataResponse:
    """Read local JSON for this same-machine example, with a bounded file read.

    The loader handles JSON parsing and caching. This fetcher deliberately
    supports only local file URLs; other deployments supply their own transport
    and authentication policy rather than forwarding processing credentials.
    """
    url = urlsplit(href)
    if url.scheme != "file" or url.netloc not in ("", "localhost"):
        raise DiscoveryError("local-metadata", "Expected a local file URL")
    path = Path(url2pathname(url.path))
    content = await asyncio.wait_for(
        asyncio.to_thread(_read_metadata, path, max_bytes), timeout
    )
    return MetadataResponse(content, path.resolve().as_uri(), "application/geo+json")


# --8<-- [end:fetcher]


# --8<-- [start:composition]
class ProductFolderResolver(ComposedJobResultResolver):
    """Make a known CSV inside the test processes' products folder selectable.

    Reuse STAC recognition and declare the folder layout rather than scanning
    storage. The process predicate keeps this interpretation local to the demo.
    """

    def __init__(self):
        folder = FolderResourceTransformer(
            entries=(
                ResourceEntry(
                    key="tables",
                    location="tables",
                    kind="container",
                    children=(
                        ResourceEntry(
                            key="observations",
                            location="observations.csv",
                            title="Configured observations",
                            media_type="text/csv",
                            roles=("data",),
                        ),
                    ),
                ),
            ),
            matches=lambda resource, context: resource.key == "products",
            config_id="testing-products",
            config_revision="1",
        )
        super().__init__(
            StacResolver(),
            (folder,),
            accepts=lambda context: (
                context.process_description is not None
                and context.process_description.id
                in {"simulate_stac_item", "simulate_stac_item_collection"}
            ),
        )


# --8<-- [end:composition]


async def example_session() -> None:
    """Run inline, linked, and configured discovery, then release demo resources."""
    with TemporaryDirectory(prefix="cuiman-results-") as output_dir:
        root = Path(output_dir)
        client = create_client(root / "client-config.yaml")
        try:
            # --8<-- [start:inline-call]
            job_id, results, process = await submit_stac(
                client, "simulate_stac_item", root / "inline"
            )
            print(results.model_dump_json(indent=2))
            resources = await discover_output(client, job_id, results, process)
            print(resources)
            # --8<-- [end:inline-call]

            # --8<-- [start:open-call]
            resource = resources.select(key="data")
            table = await client.open_job_result(resource, data_type=pd.DataFrame)
            print(table)
            # --8<-- [end:open-call]

            # --8<-- [start:composition-call]
            unregister = client.config.register_job_result_resolver(
                ProductFolderResolver
            )
            try:
                expanded = await discover_output(client, job_id, results, process)
            finally:
                unregister()
            configured = expanded.select(key="observations")
            print(await client.open_job_result(configured, data_type=pd.DataFrame))
            # --8<-- [end:composition-call]

            # --8<-- [start:linked-call]
            job_id, results, process = await submit_stac(
                client, "simulate_stac_item_collection", root / "linked"
            )
            loader = MetadataLoader(fetch_local_metadata)
            resources = await discover_output(
                client, job_id, results, process, loader=loader
            )
            print(resources)
            resource = resources.select(item_id="ndvi-2026-09-02", key="data")
            print(await client.open_job_result(resource, data_type=pd.DataFrame))
            print(f"Metadata fetches: {loader.request_count}")
            # --8<-- [end:linked-call]
        finally:
            await client.close()


def _read_metadata(path: Path, max_bytes: int) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(max_bytes)
        if stream.read(1):
            raise DiscoveryError(
                "byte-limit", "Metadata response size limit reached", partial=True
            )
    return content


if __name__ == "__main__":
    asyncio.run(example_session())
