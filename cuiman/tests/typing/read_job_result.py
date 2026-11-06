"""Static client return-type assertions checked by ``pixi run typecheck``."""

from typing import Any, assert_type

from pystac import Asset

from cuiman import AsyncClient, Client


class Representation:
    """A representation supplied by an application reader."""


def check_sync(client: Client, asset: Asset) -> None:
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


async def check_async(client: AsyncClient, asset: Asset) -> None:
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
