"""Deprecated client methods forward calls to the current reader API."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from pystac import Asset

from cuiman import AsyncClient, Client
from cuiman.api.reader import JobResultReadError
from gavicore.models.core import JobResults


@pytest_asyncio.fixture(params=[Client, AsyncClient])
async def client(request):
    instance = request.param(api_url="https://process.test", auth={"auth_type": "none"})
    try:
        yield instance
    finally:
        if isinstance(instance, AsyncClient):
            await instance.close()
        else:
            instance.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args,kwargs",
    [
        (("job",), {}),
        ((), {"job_id_or_asset": "job", "output_name": "result", "data_type": dict}),
        (
            ("job", "result", dict, "application/json", 0.25, 30),
            {"reader_id": "custom", "chunks": {"time": 1}},
        ),
        ((Asset("https://data.test/report.csv"),), {"reader_id": "pandas"}),
        ((JobResults(root={"result": None}),), {"output_name": "result"}),
    ],
)
async def test_open_job_result_warns_at_caller_and_forwards_unchanged(
    client, monkeypatch, args, kwargs
):
    expected = object()
    method = AsyncMock if isinstance(client, AsyncClient) else Mock
    read = method(return_value=expected)
    monkeypatch.setattr(client, "read_job_result", read)

    with pytest.warns(
        DeprecationWarning,
        match=r"open_job_result\(\) is deprecated since version 0\.5\.0; .*read_job_result\(\)",
    ) as warnings:
        if isinstance(client, AsyncClient):
            result = await client.open_job_result(*args, **kwargs)
        else:
            result = client.open_job_result(*args, **kwargs)

    assert result is expected
    read.assert_called_once_with(*args, **kwargs)
    if isinstance(client, AsyncClient):
        read.assert_awaited_once_with(*args, **kwargs)
    assert len(warnings) == 1
    assert Path(warnings[0].filename).resolve() == Path(__file__).resolve()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [JobResultReadError("unreadable"), TypeError("invalid target")]
)
async def test_open_job_result_preserves_reader_errors(client, monkeypatch, error):
    method = AsyncMock if isinstance(client, AsyncClient) else Mock
    read = method(side_effect=error)
    monkeypatch.setattr(client, "read_job_result", read)

    with pytest.warns(DeprecationWarning, match="read_job_result"):
        with pytest.raises(type(error)) as caught:
            if isinstance(client, AsyncClient):
                await client.open_job_result("job")
            else:
                client.open_job_result("job")
    assert caught.value is error
    read.assert_called_once_with("job")
