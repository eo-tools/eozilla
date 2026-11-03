"""Check the STAC guide's transformations, client calls, and cleanup offline."""

import runpy
from datetime import datetime, timezone
from unittest.mock import Mock, call

import pandas as pd
import pystac
import pytest

from cuiman import Client, ClientConfig
from cuiman.api.opener import JobResultOpenContext
from examples.guides.cuiman import stac
from gavicore.models.core import JobInfo, JobResults, ProcessDescription, ProcessRequest


@pytest.fixture
def item():
    result = pystac.Item("scene-1", None, None, datetime.now(timezone.utc), {})
    result.add_asset("report", pystac.Asset("report.csv", media_type="text/csv"))
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("collection", [False, True])
async def test_mark_reviewed_returns_native_object(item, collection):
    value = pystac.ItemCollection([item]) if collection else item
    ctx = JobResultOpenContext(config=ClientConfig(), value=value)
    assert await stac.mark_reviewed(value, ctx) is value
    member = value[0] if collection else value
    assert member.properties["demo:reviewed"] is True
    catalog = pystac.Catalog("catalog", "No Items to mark")
    assert await stac.mark_reviewed(catalog, ctx) is catalog


@pytest.mark.parametrize(
    "process_id,output_name,accepted",
    [
        (None, "item", False),
        ("other", "item", False),
        ("create_inline_stac", "report", False),
        ("create_inline_stac", "item", True),
        ("create_linked_stac", "item_collection", True),
    ],
)
def test_predicate_limits_demo_transformation(process_id, output_name, accepted):
    ctx = JobResultOpenContext(
        config=ClientConfig(),
        value=None,
        process_description=(
            ProcessDescription(id=process_id, version="1") if process_id else None
        ),
        output_name=output_name,
    )
    assert stac.accepts_testing_stac(ctx) is accepted


@pytest.mark.parametrize("process_id", ["create_inline_stac", "create_linked_stac"])
def test_run_one_selects_outputs_and_reads_exact_report(item, process_id, capsys):
    item.properties["demo:reviewed"] = True
    client = Mock(spec=Client)
    client.execute_process.return_value = JobInfo(jobID="demo-job", status="successful")
    client.open_job_result.side_effect = [
        item,
        pystac.ItemCollection([item]),
        pd.DataFrame({"mean_ndvi": [1.5]}),
    ]
    client.get_job_results.return_value = JobResults(root={"item": item.to_dict()})

    assert stac.run_one(client, process_id) == "demo-job"

    client.execute_process.assert_called_once_with(
        process_id, request=ProcessRequest(inputs={"item_count": 2})
    )
    assert client.open_job_result.call_args_list[0].args == ("demo-job",)
    assert client.open_job_result.call_args_list[0].kwargs == {
        "output_name": "item",
        "data_type": pystac.Item,
    }
    assert client.open_job_result.call_args_list[1].kwargs == {
        "output_name": "item_collection",
        "data_type": pystac.ItemCollection,
    }
    assert client.open_job_result.call_args.args == (item.assets["report"],)
    assert client.open_job_result.call_args.kwargs == {"data_type": pd.DataFrame}
    client.get_job_results.assert_called_once_with("demo-job")
    assert "report.csv [1.5]" in capsys.readouterr().out


@pytest.mark.parametrize("fails", [False, True])
def test_main_closes_client_after_success_or_failure(monkeypatch, fails):
    client = Mock(spec=Client)
    constructor = Mock(return_value=client)
    run_one = Mock(side_effect=RuntimeError("unavailable") if fails else None)
    monkeypatch.setattr(stac, "Client", constructor)
    monkeypatch.setattr(stac, "run_one", run_one)
    if fails:
        with pytest.raises(RuntimeError, match="unavailable"):
            stac.main()
    else:
        stac.main()
        assert run_one.call_args_list == [
            call(client, "create_inline_stac"),
            call(client, "create_linked_stac"),
        ]
    assert constructor.call_args.kwargs["config_type"] is stac.DemoClientConfig
    client.close.assert_called_once()


def test_script_entry_point_closes_client(monkeypatch):
    client = Mock(spec=Client)
    client.execute_process.side_effect = RuntimeError("offline")
    monkeypatch.setattr("cuiman.Client", Mock(return_value=client))
    with pytest.raises(RuntimeError, match="offline"):
        runpy.run_path(stac.__file__, run_name="__main__")
    client.close.assert_called_once()
