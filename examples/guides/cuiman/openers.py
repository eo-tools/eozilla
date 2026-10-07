"""Submit a small scene and open its Zarr output on the same machine.

Run with ``python -m examples.guides.cuiman.openers`` from the repository root.
The local test server writes the requested directory, replacing existing data.
"""

# --8<-- [start:imports]
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import xarray as xr

from cuiman import Client
from cuiman.api.opener import JobResultOpenContext, JobResultOpener
from gavicore.models import ProcessRequest

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
        engine="zarr",
        timeout=30,
        poll_interval=0.1,
    )


# --8<-- [end:builtin]


# --8<-- [start:custom]
class LocalZarrOpener(JobResultOpener):
    """Open local Zarr links as datasets, converting file URIs to native paths."""

    async def accept_job_result(self, ctx: JobResultOpenContext) -> bool:
        """Accept the selected output only if it is a local Zarr dataset."""
        link = ctx.output_link
        if link is None or ctx.data_type not in (None, xr.Dataset):
            return False
        url = urlsplit(link.href)
        return (
            ctx.output_media_type == "application/zarr"
            and url.scheme == "file"
            and url.netloc in ("", "localhost")
        )

    async def open_job_result(self, ctx: JobResultOpenContext) -> xr.Dataset:
        """Pass the native filesystem path and reader options to xarray."""
        link = ctx.output_link
        assert link is not None
        path = url2pathname(urlsplit(link.href).path)
        return xr.open_zarr(path, **ctx.options)


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
    client = Client(api_url="http://127.0.0.1:8008", auth={"auth_type": "none"})
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
        return job_id
    finally:
        # --8<-- [start:close]
        client.close()
        # --8<-- [end:close]


if __name__ == "__main__":
    example_session()
