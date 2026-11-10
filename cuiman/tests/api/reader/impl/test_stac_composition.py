from copy import deepcopy
from unittest.mock import patch

import pystac
import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.reader import JobResultReadContext, JobResultReadError
from cuiman.api.reader.impl import StacJobResultReader, compose_stac_reader
from cuiman.api.reader.reader import read_job_result


def _document():
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "id": "scene",
        "geometry": None,
        "bbox": None,
        "properties": {"datetime": "2026-01-01T00:00:00Z"},
        "links": [{"rel": "self", "href": "https://data.test/results/item.json"}],
        "assets": {"report": {"href": "report.csv", "type": "text/csv"}},
    }


@pytest.mark.asyncio
async def test_order_predicate_and_repeated_independent_results():
    source = _document()
    original = deepcopy(source)
    events = []

    async def first(stac, ctx):
        events.append(("first", ctx.output_name))
        stac.properties["project:reviewed"] = True
        return stac

    async def second(stac, ctx):
        events.append(("second", stac.properties["project:reviewed"]))
        stac.assets["report"].title = "Reviewed report"
        return stac

    Composed = compose_stac_reader(
        StacJobResultReader,
        transformers=(first, second),
        accepts=lambda ctx: ctx.output_name == "item",
    )
    ctx = JobResultReadContext(config=ClientConfig(), value=source, output_name="item")
    with patch.object(
        pystac.stac_io.DefaultStacIO,
        "read_json",
        side_effect=AssertionError("metadata fetch forbidden"),
    ):
        result = await read_job_result(ctx, Composed, StacJobResultReader)
        again = await read_job_result(ctx, Composed, StacJobResultReader)
    assert events == [("first", "item"), ("second", True)] * 2
    assert result.assets["report"].owner is result
    assert result.assets["report"].title == "Reviewed report"
    result.assets["report"].title = "Changed later"
    assert again.assets["report"].title == "Reviewed report"
    assert source == original
    ctx.output_name = "other"
    ordinary = await read_job_result(ctx, Composed, StacJobResultReader)
    assert "project:reviewed" not in ordinary.properties
    assert len(events) == 4


@pytest.mark.asyncio
async def test_failed_stage_does_not_mutate_previous_stage_or_fall_back():
    seen = []

    async def first(stac, ctx):
        seen.append(stac)
        stac.properties["project:ok"] = True
        return stac

    async def fail(stac, ctx):
        stac.properties["project:bad"] = True
        raise ValueError("signed-url-token")

    Composed = compose_stac_reader(StacJobResultReader, transformers=(first, fail))
    ctx = JobResultReadContext(config=ClientConfig(), value=_document())
    with pytest.raises(JobResultReadError) as error:
        await read_job_result(ctx, Composed, StacJobResultReader)
    assert "signed-url-token" not in str(error.value) + str(error.value.__cause__)
    assert seen[0].properties["project:ok"] is True
    assert "project:bad" not in seen[0].properties


@pytest.mark.asyncio
@pytest.mark.parametrize("broken", ["none", "owner", "predicate"])
async def test_invalid_transformations_are_terminal_and_sanitized(broken):
    async def transform(stac, ctx):
        if broken == "none":
            return None
        stac.assets["report"].set_owner(None)
        return stac

    def accepts(ctx):
        if broken == "predicate":
            raise ValueError("signed-url-token")
        return True

    Composed = compose_stac_reader(
        StacJobResultReader, transformers=(transform,), accepts=accepts
    )
    with pytest.raises(JobResultReadError) as error:
        await read_job_result(
            JobResultReadContext(config=ClientConfig(), value=_document()),
            Composed,
            StacJobResultReader,
        )
    assert "signed-url-token" not in str(error.value) + str(error.value.__cause__)


@pytest.mark.asyncio
async def test_requested_native_type_is_preserved():
    async def change_type(stac, ctx):
        return pystac.Catalog("different", "different")

    Composed = compose_stac_reader(StacJobResultReader, transformers=(change_type,))
    ctx = JobResultReadContext(
        config=ClientConfig(), value=_document(), data_type=pystac.Item
    )
    with pytest.raises(JobResultReadError, match="transformation failed"):
        await read_job_result(ctx, Composed, StacJobResultReader)


def test_composition_rejects_invalid_registration():
    with pytest.raises(TypeError, match="callable transformers"):
        compose_stac_reader(StacJobResultReader, transformers=())
    with pytest.raises(TypeError, match="acceptance predicate"):
        compose_stac_reader(
            StacJobResultReader, transformers=(lambda stac, ctx: stac,), accepts=3
        )


@pytest.mark.asyncio
async def test_composed_reader_reports_missing_stac_dependency():
    async def transform(stac, ctx):
        return stac

    Composed = compose_stac_reader(StacJobResultReader, transformers=(transform,))
    ctx = JobResultReadContext(config=ClientConfig(), value=_document())
    with patch("cuiman.api.reader.impl.base.find_spec", return_value=None):
        with pytest.raises(JobResultReadError, match=r"cuiman\[stac\]"):
            await read_job_result(ctx, Composed)


@pytest.mark.asyncio
async def test_async_predicate_and_loaded_link_copy_without_fetching():
    async def accepts(ctx):
        return ctx.output_name == "item"

    async def link_to_loaded_object(stac, ctx):
        stac.add_link(pystac.Link(rel="related", target=stac))
        return stac

    Composed = compose_stac_reader(
        StacJobResultReader,
        transformers=(link_to_loaded_object,),
        accepts=accepts,
    )
    ctx = JobResultReadContext(
        config=ClientConfig(), value=_document(), output_name="item"
    )
    with patch.object(
        pystac.stac_io.DefaultStacIO,
        "read_json",
        side_effect=AssertionError("remote navigation forbidden"),
    ):
        result = await read_job_result(ctx, Composed, StacJobResultReader)
    assert any(link.rel == "related" and link.target is result for link in result.links)


@pytest.mark.asyncio
async def test_invalid_asset_owner_in_loaded_link_is_terminal():
    async def attach_broken_target(stac, ctx):
        related = pystac.Item.from_dict(_document())
        related.assets["report"].set_owner(None)
        stac.add_link(pystac.Link(rel="related", target=related))
        return stac

    Composed = compose_stac_reader(
        StacJobResultReader, transformers=(attach_broken_target,)
    )
    ctx = JobResultReadContext(config=ClientConfig(), value=_document())
    with patch.object(
        pystac.stac_io.DefaultStacIO,
        "read_json",
        side_effect=AssertionError("remote navigation forbidden"),
    ):
        with pytest.raises(JobResultReadError, match="transformation failed"):
            await read_job_result(ctx, Composed, StacJobResultReader)
