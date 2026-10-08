"""Submit a small scene and open its Zarr output on the same machine.

Run with ``python -m examples.guides.cuiman.openers`` from the repository root.
The local test server writes the requested directory, replacing existing data.
"""

# --8<-- [start:imports]
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import url2pathname

import xarray as xr

from cuiman import Client
from cuiman.api import JobResultContext
from cuiman.api.opener import JobResultOpener
from cuiman.api.resources import JobResultResource, make_resource_id
from gavicore.models import Link, ProcessRequest

# --8<-- [end:imports]


# --8<-- [start:submit]
def submit_scene(client: Client, request_path: Path) -> str:
    """Load a scene request and return the newly submitted job's ID."""
    request = ProcessRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )
    job = client.execute_process("simulate_scene", request=request)
    print(job.model_dump_json(indent=2))
    return job.jobID


# --8<-- [end:submit]


# --8<-- [start:builtin]
def open_scene(client: Client, job_id: str) -> xr.Dataset:
    """Wait up to 30 seconds and use the built-in xarray opener."""
    return client.open_job_result(
        job_id,
        output_name="return_value",
        data_type=xr.Dataset,
        timeout=30,
        poll_interval=0.1,
    )


# --8<-- [end:builtin]


# --8<-- [start:resource]
def describe_scene(client: Client, job_id: str) -> JobResultResource:
    """Describe this known process's completed output for explicit selection.

    This example constructs a resource from an ordinary Link. For compound STAC
    outputs, use a resolver to discover the selectable Assets instead.
    """
    results = client.get_job_results(job_id)
    link = Link.model_validate((results.root or {})["return_value"])
    return JobResultResource(
        id=make_resource_id("return_value"),
        output_name="return_value",
        kind="link",
        link=link,
        media_type=link.type,
        discovery_state="complete",
        provenance={"job_id": job_id},
    )


def open_scene_resource(client: Client, resource: JobResultResource) -> xr.Dataset:
    """Open the supplied target directly, using this client's built-in reader."""
    return client.open_job_result(resource, data_type=xr.Dataset, chunks=None)


# --8<-- [end:resource]


# --8<-- [start:custom]
class LocalZarrOpener(JobResultOpener):
    """Open local Zarr links as datasets, converting file URIs to native paths."""

    async def accept(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> bool:
        """Accept the selected output only if it is a local Zarr dataset."""
        link = resource.link
        if link is None or context.data_type not in (None, xr.Dataset):
            return False
        url = urlsplit(link.href)
        return (
            (context.media_type_for(resource) or "").partition(";")[0].strip().lower()
            == "application/zarr"
            and url.scheme == "file"
            and url.netloc in ("", "localhost")
        )

    async def open(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> xr.Dataset:
        """Pass the native filesystem path and reader options to xarray."""
        link = resource.link
        assert link is not None
        path = url2pathname(urlsplit(link.href).path)
        return xr.open_zarr(path, **await context.reader_options(resource))


# --8<-- [end:custom]


# --8<-- [start:registration]
def open_with_custom_opener(client: Client, job_id: str) -> xr.Dataset:
    """Temporarily prefer the custom opener, restoring registration afterward."""
    unregister = client.config.register_job_result_opener(LocalZarrOpener)
    try:
        return client.open_job_result(
            job_id, output_name="return_value", data_type=xr.Dataset, timeout=30
        )
    finally:
        unregister()


# --8<-- [end:registration]


def example_session() -> str:
    """Submit one scene, print its dataset summary, and release resources."""
    # --8<-- [start:connect]
    profile = TemporaryDirectory(prefix="cuiman-opener-profile-")
    client = Client(
        config_path=str(Path(profile.name) / "client-config.yaml"),
        api_url="http://127.0.0.1:8008",
        auth={"auth_type": "none"},
    )
    # --8<-- [end:connect]
    try:
        # --8<-- [start:submit-call]
        request_path = Path("examples/guides/cuiman/simulate-scene-request.json")
        job_id = submit_scene(client, request_path)
        # --8<-- [end:submit-call]

        # --8<-- [start:open-call]
        dataset = open_scene(client, job_id)
        try:
            print(dataset)
            print(dict(dataset.sizes))
        finally:
            dataset.close()
        # --8<-- [end:open-call]

        # --8<-- [start:resource-call]
        resource = describe_scene(client, job_id)
        dataset = open_scene_resource(client, resource)
        try:
            print(dataset)
        finally:
            dataset.close()
        # --8<-- [end:resource-call]
        return job_id
    finally:
        # --8<-- [start:close]
        client.close()
        profile.cleanup()
        # --8<-- [end:close]


if __name__ == "__main__":
    example_session()
