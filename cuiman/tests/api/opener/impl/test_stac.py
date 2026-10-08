import asyncio
import subprocess
import sys
from copy import deepcopy
from unittest.mock import patch

import httpx2
import pystac
import pytest
from tests.helpers import AllOpener

from cuiman.api.config import ClientConfig
from cuiman.api.opener import JobResultOpenContext, JobResultOpenError, StacMetadataIO
from cuiman.api.opener.impl import StacJobResultOpener
from cuiman.api.opener.impl._stac import _BoundedStacIO, _resolve_href
from cuiman.api.opener.opener import open_job_result
from gavicore.models import (
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
    Schema,
)


def item(href="data.zarr"):
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "stac_extensions": ["https://example.test/unknown-extension.json"],
        "id": "scene",
        "geometry": None,
        "bbox": None,
        "properties": {"datetime": "2026-01-01T00:00:00Z", "unknown:value": 7},
        "links": [],
        "assets": {
            "data": {
                "href": href,
                "type": "application/zarr",
                "roles": ["data"],
                "unknown:setting": {"a": 1},
            }
        },
        "unknown:field": True,
    }


def context(value, **kwargs):
    return JobResultOpenContext(
        config=ClientConfig(api_url="https://process.test"), value=value, **kwargs
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True, "raw"])
async def test_item_preserves_source_and_native_owner(wrapped):
    source = item()
    source["links"] = [
        {"rel": "self", "href": "https://data.test/results/item.json"},
        {"rel": "parent", "href": "catalog.json"},
        {"rel": "preview", "href": "thumb.png"},
    ]
    original = deepcopy(source)
    value = source
    if wrapped is True:
        value = QualifiedValue(value=source, mediaType="application/geo+json")
    elif wrapped == "raw":
        value = {"value": source, "mediaType": "application/geo+json"}
    ctx = context(value, data_type=pystac.Item)
    with patch.object(
        StacMetadataIO,
        "async_read_text_with_href",
        side_effect=AssertionError("unexpected read"),
    ):
        result = await open_job_result(ctx, StacJobResultOpener)
    assert isinstance(result, pystac.Item)
    assert source == original
    assert result.assets["data"].owner is result
    assert result.assets["data"].href == "https://data.test/results/data.zarr"
    assert result.extra_fields["unknown:field"] is True
    assert result.properties["unknown:value"] == 7
    assert result.assets["data"].extra_fields["unknown:setting"] == {"a": 1}
    assert result.stac_extensions == original["stac_extensions"]
    assert (
        result.get_single_link("parent").target
        == "https://data.test/results/catalog.json"
    )
    assert result._stac_io is not None


@pytest.mark.asyncio
async def test_item_collection_containing_base_and_extra_fields():
    embedded = item()
    embedded["links"] = [
        {"rel": "self", "href": "https://unrelated.test/other.json"},
        {"rel": "parent", "href": "parent.json"},
    ]
    document = {
        "type": "FeatureCollection",
        "features": [embedded, item()],
        "links": [{"rel": "next", "href": "page2.json"}],
        "context": {"matched": 100},
        "unknown:field": 42,
    }
    ctx = context(
        document,
        document_href="https://data.test/results/job.json",
        data_type=pystac.ItemCollection,
    )
    result = await open_job_result(ctx, StacJobResultOpener)
    assert len(result) == 2
    assert all(
        member.assets["data"].href == "https://data.test/results/data.zarr"
        for member in result
    )
    assert all(
        member.assets["data"].owner is member and member._stac_io for member in result
    )
    assert result.extra_fields["context"]["matched"] == 100
    assert (
        result.extra_fields["links"][0]["href"]
        == "https://data.test/results/page2.json"
    )
    assert result.extra_fields["unknown:field"] == 42
    assert document["features"][0]["assets"]["data"]["href"] == "data.zarr"


@pytest.mark.asyncio
@pytest.mark.parametrize("collection", [False, True])
async def test_catalog_and_collection_lazy_links(collection):
    document = {
        "type": "Collection" if collection else "Catalog",
        "stac_version": "1.1.0",
        "id": "test",
        "description": "test",
        "links": [
            {"rel": "child", "href": "child.json"},
            {"rel": "item", "href": "item.json"},
        ],
        "unknown:test": 2,
    }
    if collection:
        document.update(
            license="proprietary",
            extent={
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [[None, None]]},
            },
            assets={"report": {"href": "report.csv", "type": "text/csv"}},
            item_assets={"potential": {"type": "image/tiff"}},
        )
    result = await open_job_result(
        context(
            document,
            document_href="https://data.test/catalog.json",
            data_type=pystac.Catalog,
        ),
        StacJobResultOpener,
    )
    assert isinstance(result, pystac.Collection if collection else pystac.Catalog)
    assert result.get_single_link("child").target == "https://data.test/child.json"
    assert not result.get_single_link("child").is_resolved()
    assert result.extra_fields["unknown:test"] == 2
    if collection:
        assert list(result.assets) == ["report"]
        assert result.assets["report"].owner is result
        assert result.assets["report"].href == "https://data.test/report.csv"
        assert "potential" in result.item_assets


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,datatype,media,expected",
    [
        (None, None, None, False),
        (5, None, None, False),
        ({"type": "Feature", "properties": {}, "geometry": None}, None, None, False),
        ({"type": "FeatureCollection", "features": []}, None, None, False),
        (item(), dict, None, False),
        (item(), pystac.Item, None, True),
        (Link(href="https://test/a.json"), None, None, True),
        (
            Link(
                href="https://test/no-suffix",
                type="application/geo+json; charset=utf-8",
            ),
            None,
            None,
            True,
        ),
        (Link(href="https://test/a.csv", type="text/csv"), None, None, False),
        (Link(href="https://test/a.json", type="text/csv"), None, None, False),
        (Link(href="https://test/a"), pystac.ItemCollection, None, True),
    ],
)
async def test_acceptance_has_no_io(value, datatype, media, expected):
    ctx = context(value, data_type=datatype, _media_type=media)
    with patch.object(
        ClientConfig,
        "create_stac_metadata_io",
        side_effect=AssertionError("no access in acceptance"),
    ):
        assert await StacJobResultOpener().accept_job_result(ctx) is expected


@pytest.mark.asyncio
async def test_schema_hint_and_empty_requested_collection():
    value = {"type": "FeatureCollection", "features": []}
    description = ProcessDescription(
        id="arbitrary",
        version="1.0",
        outputs={
            "output": OutputDescription(
                schema=Schema(**{"$ref": "https://schemas.stacspec.org/example.json"})
            )
        },
    )
    ctx = context(value, output_name="output", process_description=description)
    result = await open_job_result(ctx, StacJobResultOpener)
    assert isinstance(result, pystac.ItemCollection) and len(result) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,base,datatype,message",
    [
        (item(), None, None, "no containing document base"),
        ({"type": "Feature", "stac_version": "1.1.0"}, None, None, "parsing failed"),
        (item("https://data.test/a"), None, pystac.Collection, "requested native type"),
        (
            {
                "type": "FeatureCollection",
                "features": [{"stac_version": "1.1.0", "type": "Feature"}, {}],
            },
            "https://test/items.json",
            None,
            "contain STAC Items",
        ),
        (
            {**item(), "links": [{"rel": "self", "href": "relative.json"}]},
            None,
            None,
            "must be absolute",
        ),
        (
            {
                **item(),
                "links": [
                    {"rel": "self", "href": "https://a.test/a"},
                    {"rel": "self", "href": "https://b.test/a"},
                ],
            },
            None,
            None,
            "ambiguous",
        ),
    ],
)
async def test_strong_failures_do_not_fallback(value, base, datatype, message):
    with patch.object(AllOpener, "open_job_result") as fallback:
        with pytest.raises(JobResultOpenError, match=message) as failure:
            await open_job_result(
                context(value, document_href=base, data_type=datatype),
                StacJobResultOpener,
                AllOpener,
            )
        assert isinstance(failure.value.__cause__, ExceptionGroup)
        fallback.assert_not_called()


@pytest.mark.asyncio
async def test_linked_redirect_base_and_navigation_policy():
    requests = []

    def handle(request):
        requests.append(str(request.url))
        if request.url.path == "/old.json":
            return httpx2.Response(302, headers={"location": "/results/item.json"})
        return httpx2.Response(200, json=item())

    class Config(ClientConfig):
        @staticmethod
        def stac_metadata_io_factory(config):
            return StacMetadataIO(
                async_transport_factory=lambda: httpx2.MockTransport(handle),
                sync_transport_factory=lambda: httpx2.MockTransport(handle),
            )

    ctx = JobResultOpenContext(
        config=Config(api_url="https://process.test"),
        value=Link(
            href="https://data.test/old.json", type="application/json; charset=utf-8"
        ),
    )
    default = pystac.StacIO._default_io
    result = await open_job_result(ctx, StacJobResultOpener)
    assert requests == [
        "https://data.test/old.json",
        "https://data.test/results/item.json",
    ]
    assert result.assets["data"].href == "https://data.test/results/data.zarr"
    assert pystac.StacIO._default_io is default
    navigated = result._stac_io.read_stac_object("https://data.test/old.json")
    assert navigated.assets["data"].href == "https://data.test/results/data.zarr"
    assert len(requests) == 4


@pytest.mark.asyncio
async def test_weak_json_failure_fallback_retains_error():
    def handle(request):
        return httpx2.Response(200, json={"type": "FeatureCollection", "features": []})

    ctx = context(Link(href="https://data.test/a.json"))
    # An empty generic GeoJSON document is not proof of STAC, even after fetching.
    ctx._stac_metadata_io = StacMetadataIO(
        async_transport_factory=lambda: httpx2.MockTransport(handle)
    )
    with pytest.raises(JobResultOpenError):
        await open_job_result(ctx, StacJobResultOpener)
    with patch.object(AllOpener, "open_job_result", return_value="fallback"):
        assert await open_job_result(ctx, StacJobResultOpener, AllOpener) == "fallback"


def test_optional_import_and_missing_dependency():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import cuiman; from cuiman.api.config import ClientConfig; ClientConfig(api_url='https://test'); assert 'pystac' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    with patch("cuiman.api.opener.impl.base.find_spec", return_value=None):
        assert not StacJobResultOpener.is_usable()
        with pytest.raises(JobResultOpenError, match=r"cuiman\[stac\]"):
            asyncio.run(
                open_job_result(
                    context(item("https://data.test/a")), StacJobResultOpener
                )
            )
        with pytest.raises(JobResultOpenError, match="No job result opener found"):
            asyncio.run(open_job_result(context(None), StacJobResultOpener))


def test_storage_uri_and_native_path_resolution(tmp_path):
    with pytest.raises(JobResultOpenError, match="not hierarchical"):
        _resolve_href("data.zarr", "urn:catalog:identifier")
    assert (
        _resolve_href("/products/data.zarr", "https://data.test/path/item.json")
        == "https://data.test/products/data.zarr"
    )
    assert (
        _resolve_href("//other.test/data", "https://data.test/path/item.json")
        == "https://other.test/data"
    )
    assert (
        _resolve_href("products/data.zarr", "s3://bucket/path/item.json?token=secret")
        == "s3://bucket/path/products/data.zarr"
    )
    assert (
        _resolve_href("https://other.test/a?signature=1", None)
        == "https://other.test/a?signature=1"
    )
    assert (
        _resolve_href(str(tmp_path / "item with spaces.json"), None)
        == (tmp_path / "item with spaces.json").as_uri()
    )
    with pytest.raises(JobResultOpenError, match="non-empty"):
        _resolve_href("", None)
    with pytest.raises(NotImplementedError):
        _BoundedStacIO(StacMetadataIO()).write_text("unused", "")


@pytest.mark.asyncio
async def test_inline_self_relative_with_known_result_base():
    document = item()
    document["links"] = [{"rel": "self", "href": "item.json"}]
    result = await open_job_result(
        context(document, document_href="https://data.test/results.json"),
        StacJobResultOpener,
    )
    assert result.assets["data"].href == "https://data.test/data.zarr"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [None, {"type": "Catalog"}, {"type": "FeatureCollection", "features": None}],
)
async def test_explicit_request_rejects_non_stac(source):
    with pytest.raises(JobResultOpenError):
        await open_job_result(
            context(source, data_type=pystac.ItemCollection), StacJobResultOpener
        )


def test_scoped_native_navigation_and_sanitized_failures():
    def handle(request):
        if request.url.path == "/child.json":
            return httpx2.Response(302, headers={"location": "/effective/child.json"})
        if request.url.path == "/effective/child.json":
            return httpx2.Response(
                200,
                json={
                    "type": "Catalog",
                    "stac_version": "1.1.0",
                    "id": "child",
                    "description": "test",
                    "links": [{"rel": "item", "href": "grandchild.json"}],
                },
            )
        if request.url.path == "/items.json":
            return httpx2.Response(
                200, json={"type": "FeatureCollection", "features": []}
            )
        if request.url.path == "/plain.json":
            return httpx2.Response(200, content="invalid-json secret=1")
        return httpx2.Response(200, json=item("https://data.test/data.zarr"))

    io = _BoundedStacIO(
        StacMetadataIO(sync_transport_factory=lambda: httpx2.MockTransport(handle))
    )
    assert io.read_text("https://data.test/item.json").startswith("{")
    catalog = io.read_stac_object("https://data.test/child.json")
    assert (
        catalog.get_single_link("item").target
        == "https://data.test/effective/grandchild.json"
    )
    assert (
        list(catalog.get_items())[0].assets["data"].href
        == "https://data.test/data.zarr"
    )
    for href, message in [
        ("items.json", "Navigation requires"),
        ("plain.json", "parsing failed"),
    ]:
        with pytest.raises(JobResultOpenError, match=message) as failure:
            io.read_stac_object("https://data.test/" + href)
        assert "secret" not in str(failure.value)


@pytest.mark.asyncio
async def test_schema_nested_hints_and_cached_linked_failure():
    schemas = [
        {"properties": {"stac_version": {"type": "string"}}},
        {
            "oneOf": [
                {"properties": {"stac_version": {"type": "string"}}},
                {"nullable": True},
            ]
        },
        {
            "properties": {
                "features": {
                    "items": {"properties": {"stac_version": {"type": "string"}}}
                }
            }
        },
    ]
    for schema in schemas:
        description = ProcessDescription(
            id="arbitrary",
            version="1.0",
            outputs={"a": OutputDescription(schema=Schema(**schema))},
        )
        ctx = context(
            {"type": "FeatureCollection", "features": []},
            output_name="a",
            process_description=description,
        )
        assert await StacJobResultOpener().accept_job_result(ctx)
    with pytest.raises(JobResultOpenError, match="not supported STAC"):
        await open_job_result(context({}, data_type=pystac.Item), StacJobResultOpener)
