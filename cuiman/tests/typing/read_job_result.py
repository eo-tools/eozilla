"""Static client return-type assertions checked by ``pixi run typecheck``."""

from typing import Any, assert_type

from pystac import Asset

from cuiman import AsyncClient, Client
from gavicore.models.core import JobResults


class Representation:
    """A representation supplied by an application reader."""


def check_sync(client: Client, asset: Asset, results: JobResults) -> None:
    """Check typed and untyped calls, including positional job arguments."""
    assert_type(client.read_job_result("job", data_type=Representation), Representation)
    assert_type(
        client.read_job_result("job", "result", data_type=Representation),
        Representation,
    )
    assert_type(client.read_job_result("job", None, Representation), Representation)
    assert_type(client.read_job_result(asset, data_type=Representation), Representation)
    assert_type(client.read_job_result("job"), Any)
    assert_type(client.read_job_result("job", data_type=None), Any)
    assert_type(client.read_job_result(asset), Any)
    assert_type(
        client.read_job_result(results, data_type=Representation), Representation
    )
    assert_type(
        client.read_job_result(results, "result", data_type=Representation),
        Representation,
    )
    assert_type(client.read_job_result(results, None, Representation), Representation)
    assert_type(
        client.read_job_result(job_id_or_asset=results, data_type=Representation),
        Representation,
    )
    assert_type(client.read_job_result(results), Any)
    assert_type(client.read_job_result(results, "result"), Any)
    assert_type(client.read_job_result(results, data_type=None), Any)


async def check_async(client: AsyncClient, asset: Asset, results: JobResults) -> None:
    """Check the representation type inferred after awaiting an async read."""
    assert_type(
        await client.read_job_result("job", data_type=Representation), Representation
    )
    assert_type(
        await client.read_job_result("job", "result", data_type=Representation),
        Representation,
    )
    assert_type(
        await client.read_job_result("job", None, Representation), Representation
    )
    assert_type(
        await client.read_job_result(asset, data_type=Representation), Representation
    )
    assert_type(await client.read_job_result("job"), Any)
    assert_type(await client.read_job_result("job", data_type=None), Any)
    assert_type(await client.read_job_result(asset), Any)
    assert_type(
        await client.read_job_result(results, data_type=Representation), Representation
    )
    assert_type(
        await client.read_job_result(results, "result", data_type=Representation),
        Representation,
    )
    assert_type(
        await client.read_job_result(results, None, Representation), Representation
    )
    assert_type(
        await client.read_job_result(job_id_or_asset=results, data_type=Representation),
        Representation,
    )
    assert_type(await client.read_job_result(results), Any)
    assert_type(await client.read_job_result(results, "result"), Any)
    assert_type(await client.read_job_result(results, data_type=None), Any)
