#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import asyncio
import json
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from cuiman.api.config import ClientConfig
from cuiman.api.resolver import (
    ComposedJobResultResolver,
    DiscoveryError,
    DiscoveryLimits,
    FolderResourceTransformer,
    MetadataLoader,
    MetadataResponse,
    ResolutionContext,
    ResourceEntry,
    ResourceTransformer,
    resolve_job_result,
)
from cuiman.api.resolver.impl import StacResolver, ValueResolver
from cuiman.api.resolver.location import resolve_location
from cuiman.api.resolver.resolver import result_listing
from cuiman.api.resources import (
    JobResultResource,
    ResourceAction,
    ResourceCapabilities,
    ResourceCapability,
)
from gavicore.models import Link, OutputDescription, QualifiedValue


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        0,
        "",
        [1, None],
        {"tables": [1, 2]},
        QualifiedValue(value={"table": []}, mediaType="application/json"),
    ],
)
async def test_fallback_preserves_every_original_value(value):
    ctx = ResolutionContext(
        "output",
        value,
        job_id="job",
        output_description=OutputDescription(title="Title", schema={"type": "object"}),
    )
    listing = await resolve_job_result(ctx)
    assert listing.discovery_state == "complete"
    assert listing[0].has_value
    expected = (
        value.model_dump(mode="json", by_alias=True)
        if isinstance(value, QualifiedValue)
        else value
    )
    assert listing[0].model_dump(mode="json")["value"] == expected
    assert listing[0].title == "Title"
    assert listing[0].provenance["job_id"] == "job"
    assert await ValueResolver().accept(ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        Link(href="https://store.test/data", type="text/csv; charset=utf-8"),
        {"href": "https://store.test/data", "type": "text/csv; charset=utf-8"},
    ],
)
async def test_ordinary_links_are_not_probed(value):
    fetch = AsyncMock()
    listing = await resolve_job_result(
        ResolutionContext("report", value, loader=MetadataLoader(fetch)), StacResolver
    )
    assert listing[0].kind == "link"
    assert not listing[0].has_value
    assert listing[0].media_type == "text/csv; charset=utf-8"
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_precedence_original_values_and_failure():
    source = {"custom": [1, 2]}

    class First(ValueResolver):
        async def accept(self, ctx):
            assert ctx.value is source
            return True

    class MustNotRun(ValueResolver):
        async def accept(self, ctx):
            raise AssertionError("Second resolver was run")

    assert (
        await resolve_job_result(ResolutionContext("x", source), First, MustNotRun)
    )[0].kind == "value"
    with pytest.raises(TypeError, match="subclass"):
        await resolve_job_result(ResolutionContext("x", None), object)
    for error, state, code in [
        (RuntimeError("SECRET"), "error", "resolver-failure"),
        (
            DiscoveryError("request-limit", "Budget reached", partial=True),
            "partial",
            "request-limit",
        ),
    ]:

        class Broken(ValueResolver):
            async def accept(self, ctx):
                raise error

        listing = await resolve_job_result(ResolutionContext("x", source), Broken)
        assert listing[0].value["custom"] == (1, 2)
        assert listing.discovery_state == state
        assert listing.diagnostics[0].code == code
        assert "SECRET" not in listing.model_dump_json()


def test_configuration_resolver_isolation_and_order():
    class First(ValueResolver):
        pass

    class Last(ValueResolver):
        pass

    class Application(ClientConfig):
        extra_job_result_resolvers = (t for t in [First, Last, First])

    class Child(Application):
        pass

    class Other(ClientConfig):
        pass

    assert Application.extra_job_result_resolvers == (First, Last, First)
    assert Application.get_job_result_resolver_registry().resolver_types == (
        First,
        Last,
        StacResolver,
        ValueResolver,
    )
    undo = Application.register_job_result_resolver(Last)
    assert Application.get_job_result_resolver_registry().resolver_types[0] is Last
    assert Child.get_job_result_resolver_registry().resolver_types[0] is First
    assert (
        Other.get_job_result_resolver_registry().resolver_types
        == ClientConfig.get_job_result_resolver_registry().resolver_types
        == (StacResolver, ValueResolver)
    )
    undo()
    undo()
    assert Application.get_job_result_resolver_registry().resolver_types == (
        First,
        StacResolver,
        ValueResolver,
    )
    assert "extra_job_result_resolvers" not in Application().to_file_dict()
    with pytest.raises(TypeError, match="subclass"):
        Application.register_job_result_resolver(object)

    class Invalid(ClientConfig):
        extra_job_result_resolvers = (object,)

    with pytest.raises(TypeError, match="subclass"):
        Invalid.get_job_result_resolver_registry().resolver_types


@pytest.mark.asyncio
async def test_metadata_deduplication_and_snapshot_isolation():
    fetch = AsyncMock(
        return_value=MetadataResponse(
            b'{"features": []}', "https://redirect.test/page.json", "application/json"
        )
    )
    loader = MetadataLoader(fetch, DiscoveryLimits(max_requests=1))
    first, second = await asyncio.gather(
        loader.load("https://source.test/page"), loader.load("https://source.test/page")
    )
    first.value["features"].append(1)
    assert second.value == {"features": []}
    assert second.base_uri == "https://redirect.test/page.json"
    assert loader.request_count == 1
    fetch.assert_awaited_once_with(
        "https://source.test/page", max_bytes=2 * 1024 * 1024, timeout=10.0
    )
    with pytest.raises(DiscoveryError, match="budget"):
        await loader.load("https://other.test/page")
    loader.clear()
    await loader.load("https://source.test/page")
    assert fetch.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,error,code",
    [
        (b"NaN", None, "invalid-json"),
        (b"\xff", None, "invalid-json"),
        (b"{broken", None, "invalid-json"),
        (b'"too large"', None, "byte-limit"),
        (None, OSError("SECRET"), "metadata-access"),
        (None, DiscoveryError("provider", "Provider unavailable"), "provider"),
    ],
)
async def test_metadata_failure_cache(response, error, code):
    fetch = AsyncMock(
        side_effect=error,
        return_value=MetadataResponse(response or b"", "https://source.test/meta"),
    )
    loader = MetadataLoader(fetch, DiscoveryLimits(max_bytes=8))
    for _ in range(2):
        with pytest.raises(DiscoveryError) as raised:
            await loader.load("https://source.test/meta")
        assert raised.value.code == code
        assert "SECRET" not in raised.value.message
    assert fetch.await_count == 1


@pytest.mark.asyncio
async def test_timeout_and_cancellation():
    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    with pytest.raises(DiscoveryError, match="TimeoutError"):
        await MetadataLoader(slow, DiscoveryLimits(timeout=0.001)).load(
            "https://source.test/meta"
        )
    fetch = AsyncMock(side_effect=asyncio.CancelledError)
    ctx = ResolutionContext(
        "x",
        Link(href="https://source.test/meta", type="application/json"),
        loader=MetadataLoader(fetch),
    )
    with pytest.raises(asyncio.CancelledError):
        await resolve_job_result(ctx, StacResolver)


def test_context_limits_validation():
    with pytest.raises(ValueError, match="positive"):
        DiscoveryLimits(max_items=0)
    with pytest.raises(ValueError, match="positive"):
        DiscoveryLimits(timeout=0)
    with pytest.raises(ValueError, match="output name"):
        ResolutionContext("", None)
    loader = MetadataLoader(AsyncMock(), DiscoveryLimits(max_items=2))
    assert ResolutionContext("x", None, loader=loader).limits is loader.limits


@pytest.mark.asyncio
async def test_stac_item_preserves_source_and_metadata():
    source = _item()
    original = deepcopy(source)
    ctx = ResolutionContext(
        "dataset", source, base_uri="https://source.test/path/item.json"
    )
    assert await StacResolver().accept(ctx)
    listing = await StacResolver().resolve(ctx)
    assert [r.kind for r in listing] == ["stac-item", "asset", "asset"]
    asset = listing.select(key="data")
    assert asset.link.href == "https://source.test/path/data.csv"
    assert asset.roles == ("data",)
    assert listing.select(key="folder").link.href == "https://source.test/path/products"
    assert listing.select(key="folder").media_type is None
    assert asset.parent_id == listing[0].id
    assert asset.item_id == "item-1"
    assert asset.capabilities.opener.state == "unknown"
    assert asset.metadata["stac_asset"]["extra"] == "kept"
    assert source == original


@pytest.mark.asyncio
async def test_referenced_stac_reuses_probe_and_containing_redirect_base():
    source = {
        "type": "FeatureCollection",
        "features": [_item("a"), _item("b")],
        "links": [],
    }
    for item in source["features"]:
        item["links"] = [{"rel": "self", "href": "https://elsewhere.test/item.json"}]
    fetch = AsyncMock(
        return_value=MetadataResponse(
            json.dumps(source).encode(), "https://redirect.test/results/page.json"
        )
    )
    ctx = ResolutionContext(
        "x",
        Link(
            href="https://source.test/meta", type="application/geo+json; charset=utf-8"
        ),
        loader=MetadataLoader(fetch),
    )
    listing = await resolve_job_result(ctx, StacResolver)
    assert fetch.await_count == 1
    assert len(listing) == 7
    assert (
        listing.select(item_id="b", key="data").link.href
        == "https://redirect.test/results/data.csv"
    )
    assert (
        listing.select(item_id="a", key="data").id
        != listing.select(item_id="b", key="data").id
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        {
            "type": "Feature",
            "geometry": None,
            "properties": {},
            "links": [],
            "assets": {},
            "id": "x",
        },
        {"type": "FeatureCollection", "features": []},
        {"type": "FeatureCollection", "features": [None]},
        12,
        {"foo": "bar"},
    ],
)
async def test_ordinary_geojson_and_json_not_misclassified(value):
    ctx = ResolutionContext("x", value)
    assert not await StacResolver().accept(ctx)
    assert (await resolve_job_result(ctx, StacResolver))[0].kind == "value"


@pytest.mark.asyncio
async def test_empty_and_mixed_collections():
    empty = ResolutionContext(
        "x", {"type": "FeatureCollection", "features": []}, stac_hint=True
    )
    listing = await resolve_job_result(empty, StacResolver)
    assert listing.discovery_state == "complete"
    assert len(listing) == 1  # Internal flat view includes its inspectable container.
    item = _item()
    item["assets"]["bad"] = {"title": "Broken"}
    source = {
        "type": "FeatureCollection",
        "features": [_item("a"), None, _item("a"), item],
        "links": [{"rel": "next", "href": "next.json"}],
    }
    listing = await resolve_job_result(
        ResolutionContext("x", source, base_uri="file:///C:/results/page.json"),
        StacResolver,
    )
    assert listing.discovery_state == "partial"
    assert {d.code for d in listing.diagnostics} == {
        "invalid-item",
        "duplicate-item",
        "next-page",
    }
    assert listing.select(item_id="item-1", key="bad").discovery_state == "error"
    assert (
        listing.select(item_id="item-1", key="data").link.href
        == "file:///C:/results/data.csv"
    )


@pytest.mark.asyncio
async def test_schema_hints_and_mismatch():
    schema = {
        "$ref": "https://schemas.stacspec.org/v1.1.0/item-spec/json-schema/item.json"
    }
    ctx = ResolutionContext(
        "x", {"ordinary": True}, output_description=OutputDescription(schema=schema)
    )
    listing = await resolve_job_result(ctx, StacResolver)
    assert listing[0].kind == "value"
    assert listing.diagnostics[0].code == "stac-mismatch"
    for hint in [
        {"oneOf": [schema, {"type": "string"}]},
        {"anyOf": [schema, schema]},
        {"allOf": [schema, {"type": "object"}]},
        {"$defs": {"item": schema}, "$ref": "#/$defs/item"},
        {
            "properties": {
                "type": {"enum": ["FeatureCollection"]},
                "features": {"items": schema},
            }
        },
    ]:
        assert await StacResolver().accept(
            ResolutionContext(
                "x", _item(), output_description=OutputDescription(schema=hint)
            )
        )
    cycle = {"$defs": {"loop": {"$ref": "#/$defs/loop"}}, "$ref": "#/$defs/loop"}
    assert not await StacResolver().accept(
        ResolutionContext("x", None, output_description=OutputDescription(schema=cycle))
    )
    union = OutputDescription(schema={"oneOf": [schema, {"type": "object"}]})
    assert not await StacResolver().accept(
        ResolutionContext("x", {"ordinary": True}, output_description=union)
    )


@pytest.mark.asyncio
async def test_qualified_stac_self_base_versions_and_extensions():
    item = _item()
    item["links"] = [{"rel": "self", "href": "s3://bucket/results/item.json"}]
    item["stac_version"] = "9.0.0"
    item["stac_extensions"] = ["https://extensions.test/custom"]
    for value in [
        QualifiedValue(value=item, mediaType="application/json"),
        {"value": item, "mediaType": "application/json"},
    ]:
        listing = await resolve_job_result(ResolutionContext("x", value), StacResolver)
        assert listing.select(key="data").link.href == "s3://bucket/results/data.csv"
        assert {d.code for d in listing.diagnostics} == {
            "stac-version",
            "stac-extensions",
        }
    item["links"].append({"rel": "self", "href": "https://different.test/meta"})
    listing = await resolve_job_result(ResolutionContext("x", item), StacResolver)
    assert listing.select(key="data").diagnostics[0].code == "missing-base"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Catalog", "Collection"])
async def test_containers_do_not_crawl_or_materialize_templates(kind):
    source = {
        "type": kind,
        "id": "container",
        "stac_version": "1.1.0",
        "description": "dataset",
        "links": [{"rel": "child", "href": "https://source.test/child"}],
        "extent": {},
        "license": "proprietary",
        "item_assets": {"template": {"type": "text/csv"}},
        "assets": {"data": {"href": "s3://bucket/data", "type": "text/csv"}},
    }
    fetch = AsyncMock()
    listing = await resolve_job_result(
        ResolutionContext("x", source, loader=MetadataLoader(fetch)), StacResolver
    )
    assert listing[0].discovery_state == "unresolved"
    assert len(listing) == (2 if kind == "Collection" else 1)
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_initial_discovery_limits_and_missing_loader():
    source = {
        "type": "FeatureCollection",
        "features": [_item("a"), _item("b")],
        "links": [],
    }
    listing = await resolve_job_result(
        ResolutionContext("x", source, limits=DiscoveryLimits(max_items=1)),
        StacResolver,
    )
    assert listing.diagnostics[0].code == "item-limit"
    limited = await resolve_job_result(
        ResolutionContext("x", source, limits=DiscoveryLimits(max_resources=1)),
        StacResolver,
    )
    assert len(limited) == 1 and limited.discovery_state == "partial"
    missing = await resolve_job_result(
        ResolutionContext(
            "x", Link(href="https://source.test/meta", type="application/json")
        ),
        StacResolver,
    )
    assert (
        missing[0].kind == "link" and missing.diagnostics[0].code == "metadata-loader"
    )


@pytest.mark.parametrize(
    "location,base,folder,expected",
    [
        (
            "ndvi.tif",
            "file:///C:/results/products",
            True,
            "file:///C:/results/products/ndvi.tif",
        ),
        ("a b.csv", "s3://bucket/products", True, "s3://bucket/products/a%20b.csv"),
        (
            "../data.csv",
            "https://store.test/path/item.json",
            False,
            "https://store.test/data.csv",
        ),
        ("data.csv", "gs://bucket/path/item.json", False, "gs://bucket/path/data.csv"),
        ("data.csv", "C:\\results\\products", True, "C:\\results\\products\\data.csv"),
        ("data.csv", "/results/products", True, "/results/products/data.csv"),
        ("data.csv", "/results/item.json", False, "/results/data.csv"),
        ("s3://other/data", "file:///C:/products", True, "s3://other/data"),
        ("C:\\elsewhere\\data", None, True, "C:\\elsewhere\\data"),
        (
            "data.csv?version=2",
            "https://store.test/products?token=old",
            True,
            "https://store.test/products/data.csv?version=2",
        ),
    ],
)
def test_location_resolution(location, base, folder, expected):
    assert resolve_location(location, base, folder=folder) == expected


@pytest.mark.parametrize(
    "location,base,code",
    [
        ("", None, "invalid-location"),
        ("data.csv", None, "missing-base"),
        ("data.csv", "relative/base", "ambiguous-base"),
        ("data.csv", "opaque:base", "ambiguous-base"),
    ],
)
def test_location_base_errors(location, base, code):
    with pytest.raises(DiscoveryError) as error:
        resolve_location(location, base, folder=True)
    assert error.value.code == code


@pytest.mark.asyncio
async def test_folder_chain_provenance_and_refresh_identity():
    source = _item()
    before = deepcopy(source)
    entries = (
        ResourceEntry(
            "rasters",
            "rasters",
            kind="container",
            children=(
                ResourceEntry(
                    "ndvi",
                    "ndvi.tif",
                    media_type="image/tiff",
                    roles=("data",),
                    open_hints={"xarray": {"engine": "rasterio"}},
                ),
            ),
        ),
        ResourceEntry(
            "summary",
            "s3://other/summary.csv",
            media_type="text/csv",
            access={"store": "other"},
        ),
    )
    folder = FolderResourceTransformer(
        entries,
        matches=lambda r, ctx: r.key == "folder",
        config_id="project",
        config_revision="2",
    )

    class Enrich(ResourceTransformer):
        async def transform(self, resource, ctx):
            return (
                (resource.with_updates(title="Configured NDVI"),)
                if resource.key == "ndvi"
                else (resource,)
            )

    resolver = ComposedJobResultResolver(
        StacResolver(), [folder, Enrich()], accepts=lambda ctx: ctx.output_name == "x"
    )
    assert not await resolver.accept(ResolutionContext("other", source))
    ctx = ResolutionContext("x", source, base_uri="file:///C:/results/item.json")
    assert await resolver.accept(ctx)
    first = await resolver.resolve(ctx)
    ndvi = first.select(key="ndvi")
    assert ndvi.link.href == "file:///C:/results/products/rasters/ndvi.tif"
    assert ndvi.parent_id == first.select(key="rasters").id
    assert first.select(key="rasters").parent_id == first.select(key="folder").id
    assert ndvi.item_id == "item-1" and ndvi.title == "Configured NDVI"
    assert ndvi.provenance["configuration_revision"] == "2"
    assert ndvi.provenance["declared_base"] == "file:///C:/results/products/rasters"
    assert ndvi.provenance["declared_location"] == "ndvi.tif"
    assert len(ndvi.provenance["transformations"]) == 2
    assert ndvi.metadata["directory_inventory_complete"] is False
    assert first.select(key="rasters").media_type is None
    assert first.select(key="summary").access == {"store": "other"}
    assert source == before
    source["assets"]["folder"]["href"] = "file:///D:/renewed/products"
    second = await resolver.resolve(
        ResolutionContext("x", source, base_uri=ctx.base_uri)
    )
    assert second.select(key="ndvi").id == ndvi.id
    assert (
        second.select(key="ndvi").link.href
        == "file:///D:/renewed/products/rasters/ndvi.tif"
    )
    assert len(first) == len(second)


@pytest.mark.asyncio
async def test_transform_failures_preserve_sources_successes_and_cancel():
    class Broken(ResourceTransformer):
        async def transform(self, resource, ctx):
            if resource.key == "data":
                raise RuntimeError("SECRET")
            return (resource.with_updates(title="Success"),)

    resolver = ComposedJobResultResolver(StacResolver(), [Broken()])
    result = await resolver.resolve(
        ResolutionContext("x", _item(), base_uri="https://source.test/item.json")
    )
    assert result.discovery_state == "partial"
    assert result.select(key="data").link.href == "https://source.test/data.csv"
    assert result.select(key="folder").title == "Success"
    assert "SECRET" not in result.model_dump_json()

    class Cancel(ResourceTransformer):
        async def transform(self, resource, ctx):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await ComposedJobResultResolver(ValueResolver(), [Cancel()]).resolve(
            ResolutionContext("x", None)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid", ["type", "duplicate", "ownership", "limit", "sibling"]
)
async def test_invalid_transformation_outputs(invalid):
    class Invalid(ResourceTransformer):
        async def transform(self, resource, ctx):
            if invalid == "type":
                return [resource]
            if invalid == "duplicate":
                return (resource, resource)
            if invalid == "ownership":
                return (resource.with_updates(output_name="other"),)
            if invalid == "sibling":
                # An expansion may not appropriate another loaded source's ID.
                listing = await StacResolver().resolve(ctx)
                return (resource, listing[-1])
            return (resource, resource.with_updates(id="additional"))

    if invalid == "sibling":
        base, ctx = (
            StacResolver(),
            ResolutionContext("x", _item(), base_uri="https://source.test/item.json"),
        )
    else:
        base, ctx = (
            ValueResolver(),
            ResolutionContext("x", None, limits=DiscoveryLimits(max_resources=1)),
        )
    result = await ComposedJobResultResolver(base, [Invalid()]).resolve(ctx)
    assert len(result) == (3 if invalid == "sibling" else 1)
    assert result.discovery_state == "partial"


@pytest.mark.asyncio
async def test_changed_capabilities_are_invalidated_and_continuation_retained():
    capabilities = ResourceCapabilities(
        opener=ResourceCapability(
            state="available",
            runtime="python",
            candidates=(ResourceAction(id="old", title="Old"),),
        )
    )

    class Base(ValueResolver):
        async def resolve(self, ctx):
            listing = await super().resolve(ctx)
            return listing.model_copy(
                update={
                    "resources": (listing[0].with_updates(capabilities=capabilities),),
                    "continuation": "token",
                }
            )

    class Rewrite(ResourceTransformer):
        async def transform(self, resource, ctx):
            return (resource.with_updates(media_type="text/csv"),)

    result = await ComposedJobResultResolver(Base(), [Rewrite()]).resolve(
        ResolutionContext("x", [])
    )
    assert result[0].capabilities.opener.state == "unknown"
    assert result.continuation == "token"


@pytest.mark.asyncio
async def test_folder_limits_missing_config_and_bad_siblings():
    entries = (
        ResourceEntry("good", "data.csv"),
        ResourceEntry("good", "duplicate.csv"),
        ResourceEntry(
            "tree",
            "tree",
            kind="container",
            children=(ResourceEntry("deep", "deep.csv"),),
        ),
    )
    ctx = ResolutionContext(
        "x", Link(href="file:///C:/products"), limits=DiscoveryLimits(max_depth=1)
    )
    folder = FolderResourceTransformer(entries, matches=lambda r, c: True)
    result = await ComposedJobResultResolver(ValueResolver(), [folder]).resolve(ctx)
    assert result.discovery_state == "partial"
    assert result.select(key="good").link.href == "file:///C:/products/data.csv"
    assert {d.code for d in result[0].diagnostics} == {"duplicate-entry", "depth-limit"}
    missing = FolderResourceTransformer(None, matches=lambda r, c: True)
    result = await ComposedJobResultResolver(ValueResolver(), [missing]).resolve(ctx)
    assert result.diagnostics[0].code == "folder-configuration"
    no_base = FolderResourceTransformer([], matches=lambda r, c: True)
    result = await ComposedJobResultResolver(ValueResolver(), [no_base]).resolve(
        ResolutionContext("x", None)
    )
    assert result.diagnostics[0].code == "folder-base"
    original = (await ValueResolver().resolve(ctx))[0]
    limited = await folder.transform(
        original, ResolutionContext("x", None, limits=DiscoveryLimits(max_resources=1))
    )
    assert limited[0].diagnostics[0].code == "resource-limit"
    relative = (
        await ValueResolver().resolve(
            ResolutionContext("x", Link(href="relative/base"))
        )
    )[0]
    invalid = await folder.transform(relative, ctx)
    assert invalid[0].diagnostics[0].code == "ambiguous-base"
    with pytest.raises(ValueError, match="key and location"):
        ResourceEntry("", "x")
    with pytest.raises(ValueError, match="containers"):
        ResourceEntry("x", "x", children=(ResourceEntry("y", "y"),))


@pytest.mark.asyncio
async def test_probe_decline_malformed_link_and_unrecognized_collection():
    fetch = AsyncMock(
        return_value=MetadataResponse(b'{"ordinary": true}', "https://source.test/meta")
    )
    ctx = ResolutionContext(
        "x",
        Link(href="https://source.test/meta", type="application/json"),
        loader=MetadataLoader(fetch),
    )
    assert (await resolve_job_result(ctx, StacResolver))[0].kind == "link"
    assert fetch.await_count == 1
    malformed = {"href": "somewhere", "title": {"invalid": True}}
    assert (await resolve_job_result(ResolutionContext("x", malformed)))[
        0
    ].kind == "value"
    partial = {
        "type": "Collection",
        "stac_version": "1.1.0",
        "id": "c",
        "description": "c",
        "links": [],
        "extent": {},
    }
    assert not await StacResolver().accept(ResolutionContext("x", partial))
    schema = {"allOf": [{"type": "object", "properties": {"a": {"type": "string"}}}]}
    assert not await StacResolver().accept(
        ResolutionContext(
            "x",
            None,
            output_description=OutputDescription(schema=schema),
            limits=DiscoveryLimits(max_depth=1),
        )
    )


@pytest.mark.asyncio
async def test_exact_resource_limit_and_depth_limit():
    ctx = ResolutionContext(
        "x",
        _item(),
        base_uri="https://source.test/item.json",
        limits=DiscoveryLimits(max_resources=3),
    )
    assert (await StacResolver().resolve(ctx)).discovery_state == "complete"
    collection = {"type": "FeatureCollection", "features": [_item()], "links": []}
    result = await StacResolver().resolve(
        ResolutionContext("x", collection, limits=DiscoveryLimits(max_depth=1))
    )
    assert len(result) == 2
    assert (
        result.discovery_state == "partial"
        and result.diagnostics[0].code == "depth-limit"
    )
    limited = await StacResolver().resolve(
        ResolutionContext("x", _item(), limits=DiscoveryLimits(max_resources=1))
    )
    assert limited.diagnostics[0].code == "resource-limit"


def test_uri_root_references_and_windows_entries():
    assert (
        resolve_location("/assets/data.csv", "https://store.test/path/item.json")
        == "https://store.test/assets/data.csv"
    )
    assert (
        resolve_location("//other.test/data.csv", "https://store.test/path/item.json")
        == "https://other.test/data.csv"
    )
    assert (
        resolve_location("rasters\\ndvi.tif", "file:///C:/products", folder=True)
        == "file:///C:/products/rasters/ndvi.tif"
    )
    assert (
        resolve_location("/absolute/data.csv", "file:///C:/products", folder=True)
        == "/absolute/data.csv"
    )
    for timeout in [float("nan"), float("inf")]:
        with pytest.raises(ValueError, match="positive"):
            DiscoveryLimits(timeout=timeout)


@pytest.mark.asyncio
async def test_repeated_local_schema_refs_and_schema_breadth():
    reference = {
        "$ref": "https://schemas.stacspec.org/v1.1.0/item-spec/json-schema/item.json"
    }
    local = {"$ref": "#/$defs/item"}
    description = OutputDescription(
        schema={"$defs": {"item": reference}, "anyOf": [local, local]}
    )
    # Definitive schema evidence accepts before fetching even for a binary type.
    ctx = ResolutionContext(
        "x",
        Link(href="https://source.test/result", type="application/octet-stream"),
        output_description=description,
    )
    assert await StacResolver().accept(ctx)
    broad = OutputDescription(
        schema={"oneOf": [reference, {"type": "string"}, {"type": "integer"}]}
    )
    assert not await StacResolver().accept(
        ResolutionContext(
            "x", None, output_description=broad, limits=DiscoveryLimits(max_resources=1)
        )
    )


@pytest.mark.asyncio
async def test_malformed_asset_locations_and_collection_assets_preserve_siblings():
    item = _item()
    item["assets"]["bad"] = {"href": "https://[bad/asset"}
    item["links"] = [
        {"rel": "self", "href": "https://[bad/item"},
        {"rel": "parent", "href": "https://unused.test/"},
    ]
    listing = await resolve_job_result(ResolutionContext("x", item), StacResolver)
    assert listing[0].kind == "stac-item"
    assert listing.select(key="bad").discovery_state == "error"
    assert listing.select(key="data").diagnostics[0].code == "missing-base"
    collection = {
        "type": "Collection",
        "id": "c",
        "stac_version": "1.1.0",
        "description": "c",
        "links": [],
        "extent": {},
        "license": "proprietary",
        "assets": [],
    }
    listing = await resolve_job_result(ResolutionContext("x", collection), StacResolver)
    assert listing[0].kind == "stac-collection"
    assert listing.discovery_state == "partial"
    assert listing.diagnostics[0].code == "invalid-assets"


@pytest.mark.asyncio
async def test_root_asset_identity_contains_item_ancestry():
    first = await StacResolver().resolve(
        ResolutionContext("x", _item("a"), base_uri="https://source.test/meta")
    )
    second = await StacResolver().resolve(
        ResolutionContext("x", _item("b"), base_uri="https://source.test/meta")
    )
    assert first.select(key="data").id != second.select(key="data").id


@pytest.mark.asyncio
async def test_custom_resolver_can_split_non_stac_values_and_reuse_loader():
    class Tables(ValueResolver):
        async def accept(self, ctx):
            return isinstance(ctx.value, dict) and "tables" in ctx.value

        async def resolve(self, ctx):
            return result_listing(
                ctx,
                [
                    JobResultResource(
                        id=name,
                        output_name=ctx.output_name,
                        key=name,
                        kind="value",
                        value=table,
                    )
                    for name, table in ctx.value["tables"].items()
                ],
            )

    source = {"tables": {"a": [1, 2], "b": None}}
    listing = await resolve_job_result(
        ResolutionContext("x", source), Tables, StacResolver
    )
    assert len(listing) == 2
    assert listing.select(key="b").has_value and listing.select(key="b").value is None
    assert source == {"tables": {"a": [1, 2], "b": None}}

    class InspectThenDecline(ValueResolver):
        async def accept(self, ctx):
            await ctx.loader.load(ctx.value.href)
            return False

    fetch = AsyncMock(
        return_value=MetadataResponse(
            json.dumps(_item()).encode(), "https://source.test/item.json"
        )
    )
    loader = MetadataLoader(fetch)
    ctx = ResolutionContext(
        "x",
        Link(href="https://source.test/item.json", type="application/json"),
        loader=loader,
    )
    listing = await resolve_job_result(ctx, InspectThenDecline, StacResolver)
    assert listing[0].kind == "stac-item"
    assert fetch.await_count == 1


def _item(identity="item-1"):
    return {
        "type": "Feature",
        "stac_version": "1.1.0",
        "id": identity,
        "geometry": None,
        "properties": {"datetime": "2026-10-07T00:00:00Z"},
        "links": [],
        "assets": {
            "data": {
                "href": "data.csv",
                "type": "text/csv; charset=utf-8",
                "roles": ["data"],
                "extra": "kept",
            },
            "folder": {"href": "products"},
        },
    }
