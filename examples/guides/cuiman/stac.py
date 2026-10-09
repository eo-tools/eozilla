"""Open inline and linked STAC outputs with a branded Cuiman client.

Start ``pixi run serve`` first, then run
``python -m examples.guides.cuiman.stac`` from the repository root.
The testing service retains generated products until they are cleaned up there.
"""

from pathlib import Path

import pandas as pd
import pystac

from cuiman import Client, ClientConfig
from cuiman.api.opener import JobResultOpenContext
from cuiman.api.opener.impl import StacJobResultOpener, compose_stac_opener
from gavicore.models import ProcessRequest


async def mark_reviewed(stac: object, ctx: JobResultOpenContext) -> object:
    """Mark loaded Items while leaving the source result untouched."""
    items = stac.items if isinstance(stac, pystac.ItemCollection) else (stac,)
    for item in items:
        if isinstance(item, pystac.Item):
            item.properties["demo:reviewed"] = True
    return stac


def accepts_testing_stac(ctx: JobResultOpenContext) -> bool:
    """Scope the demo transform to the testing service's native STAC outputs."""
    process = ctx.process_description
    return (
        process is not None
        and process.id in {"create_inline_stac", "create_linked_stac"}
        and ctx.output_name in {"item", "item_collection"}
    )


class DemoClientConfig(ClientConfig):
    """Register a composed STAC opener without changing global Cuiman defaults."""

    default_path = Path(".pixi/cuiman-stac-example-config")
    extra_job_result_openers = (
        compose_stac_opener(
            StacJobResultOpener,
            transformers=(mark_reviewed,),
            accepts=accepts_testing_stac,
        ),
    )


def run_one(client: Client, process_id: str) -> str:
    """Submit one process and inspect raw, native, transformed, and Asset data."""
    job = client.execute_process(
        process_id, request=ProcessRequest(inputs={"item_count": 2})
    )
    item = client.open_job_result(job.jobID, output_name="item", data_type=pystac.Item)
    collection = client.open_job_result(
        job.jobID, output_name="item_collection", data_type=pystac.ItemCollection
    )
    raw = client.get_job_results(job.jobID)
    assert raw.root is not None
    report_asset = item.assets["report"]
    report = client.open_job_result(report_asset, data_type=pd.DataFrame)
    assert item.properties["demo:reviewed"] is True
    assert all(member.properties["demo:reviewed"] for member in collection)
    print(process_id, job.jobID, sorted(raw.root))
    print(item.id, [member.id for member in collection])
    print(report_asset.href, report["mean_ndvi"].tolist())
    return job.jobID


def main() -> None:
    """Exercise both testing processes and close the client afterward."""
    client = Client(
        api_url="http://127.0.0.1:8008",
        auth={"auth_type": "none"},
        config_type=DemoClientConfig,
    )
    try:
        for process_id in ("create_inline_stac", "create_linked_stac"):
            run_one(client, process_id)
    finally:
        client.close()


if __name__ == "__main__":
    main()
