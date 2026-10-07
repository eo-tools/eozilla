#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from cuiman.api import JobResultResource, JobResultResourceListing
from cuiman.api.resources import (
    AmbiguousResourceError,
    OutputDiscoveryState,
    ResourceAction,
    ResourceCapabilities,
    ResourceCapability,
    ResourceDiagnostic,
    ResourceNotFoundError,
    make_resource_id,
)
from gavicore.models import JobResults, Link


def resource(output="dataset", item="item-1", key="data", **changes):
    return JobResultResource(
        **(
            {
                "id": make_resource_id(output, "stac-item", item, "asset", key),
                "output_name": output,
                "parent_id": make_resource_id(output, "stac-item", item),
                "path": f"{output}/{item}/{key}",
                "item_id": item,
                "kind": "asset",
                "key": key,
                "link": Link(href=f"s3://results/{item}/{key}.zarr"),
                "media_type": "application/zarr; version=2",
            }
            | changes
        )
    )


def test_public_exports():
    from cuiman import JobResultResource as PublicResource
    from cuiman import JobResultResourceListing as PublicListing

    assert PublicResource is JobResultResource
    assert PublicListing is JobResultResourceListing


@pytest.mark.parametrize("value", [None, False, 0, "", [1, None], {"table": [[1]]}])
def test_present_values_round_trip(value):
    selected = resource(kind="value", link=None, value=value)
    assert selected.has_value
    serialized = selected.model_dump(mode="json")
    assert serialized["value"] == value
    restored = JobResultResource.model_validate_json(selected.model_dump_json())
    assert restored.has_value
    assert restored == selected


def test_absent_value_round_trip():
    selected = resource()
    assert not selected.has_value
    assert "value" not in selected.model_dump()
    assert "value" not in json.loads(selected.model_dump_json())
    restored = JobResultResource.model_validate(selected.model_dump())
    assert not restored.has_value


@pytest.mark.parametrize(
    "options", [{"exclude_none": True}, {"exclude_defaults": True}]
)
def test_compact_serialization_preserves_present_null(options):
    selected = resource(link=None, value=None)
    dumped = selected.model_dump(**options)
    assert "value" in dumped and dumped["value"] is None
    assert JobResultResource.model_validate(dumped).has_value
    assert "value" not in selected.model_dump(exclude={"value"}, **options)
    assert "value" not in selected.model_dump(include={"id"}, **options)


def test_serialization_respects_nested_link_filters():
    selected = resource(
        link=Link(
            href="memory://results",
            **{"x-options": {"chunks": [1, 2], "engine": "zarr"}, "extra": None},
        )
    )
    dumped = selected.model_dump(
        include={"link": {"href", "options"}},
        exclude={"link": {"options": {"engine"}}},
    )
    assert dumped == {
        "link": {"href": "memory://results", "x-options": {"chunks": [1, 2]}}
    }
    assert "extra" not in selected.model_dump(exclude_none=True)["link"]
    assert "rel" not in selected.model_dump(exclude_defaults=True)["link"]
    assert "rel" not in selected.link.model_dump(exclude_unset=True)
    assert selected.link.model_dump(include={"options"}) == {
        "options": {"chunks": [1, 2], "engine": "zarr"}
    }


def test_resource_owns_immutable_metadata_and_link():
    metadata = {"raster:bands": [{"data_type": "float32"}]}
    hints = {"xarray": {"backend_kwargs": {"consolidated": True}}}
    link = Link(
        href="s3://results/original.zarr",
        **{"x-options": {"backend_kwargs": {"consolidated": True}}},
    )
    selected = resource(metadata=metadata, open_hints=hints, link=link)
    metadata["raster:bands"][0]["data_type"] = "uint8"
    hints["xarray"]["backend_kwargs"]["consolidated"] = False
    link.href = "s3://results/replaced.zarr"
    link.options["backend_kwargs"]["consolidated"] = False
    assert selected.metadata["raster:bands"][0]["data_type"] == "float32"
    assert selected.open_hints["xarray"]["backend_kwargs"]["consolidated"] is True
    assert selected.link.href == "s3://results/original.zarr"
    assert selected.link.options["backend_kwargs"]["consolidated"] is True
    assert isinstance(selected.link, Link)
    with pytest.raises(ValidationError, match="frozen"):
        selected.title = "Changed"
    with pytest.raises(ValidationError, match="frozen"):
        selected.link.href = "changed"
    with pytest.raises(TypeError):
        selected.metadata["extra"] = 1
    with pytest.raises(TypeError):
        selected.metadata["raster:bands"][0]["data_type"] = "changed"
    with pytest.raises(TypeError):
        selected.link.options["backend_kwargs"]["consolidated"] = False


def test_immutable_values_and_link_extensions_round_trip():
    selected = resource(
        value={"tables": [{"rows": [1, None]}]},
        link=Link(href="file:///results", **{"custom": {"array": [1, 2]}}),
    )
    with pytest.raises(TypeError):
        selected.value["tables"][0]["rows"][0] = 2
    with pytest.raises(TypeError):
        selected.link.custom["array"][0] = 2
    restored = JobResultResource.model_validate_json(selected.model_dump_json())
    assert restored == selected
    assert restored.link.custom["array"] == (1, 2)


def test_link_option_alias_round_trip():
    selected = resource(
        link=Link(href="memory://results", **{"x-options": {"chunks": [1, 2]}})
    )
    dumped = selected.model_dump(mode="json", by_alias=True)
    assert dumped["link"]["x-options"] == {"chunks": [1, 2]}
    assert "options" not in dumped["link"]
    assert JobResultResource.model_validate(dumped) == selected


@pytest.mark.parametrize(
    "field", ["value", "metadata", "provenance", "access", "open_hints"]
)
def test_runtime_objects_cannot_enter_portable_fields(field):
    with pytest.raises(ValidationError):
        resource(**{field: {"runtime": object()}})


def test_runtime_fields_and_new_schema_versions_rejected():
    with pytest.raises(ValidationError, match="Extra inputs"):
        resource(client=object())
    with pytest.raises(ValidationError, match="Input should be 1"):
        resource(schema_version=2)
    with pytest.raises(ValidationError):
        resource(link=Link(href="file:///results", **{"session": object()}))


def test_updates_revalidate_and_preserve_original_and_identity():
    selected = resource(metadata={"nested": {"value": [1]}}, value=None)
    updated = selected.with_updates(
        link=Link(href="s3://results/renewed.zarr?signature=new"),
        metadata={"nested": {"value": [2]}},
        kind="project-dataset",
    )
    assert updated.id == selected.id
    assert updated.path == selected.path
    assert updated.has_value and updated.value is None
    assert updated.link.href.endswith("signature=new")
    assert selected.link.href.endswith("data.zarr")
    assert selected.metadata["nested"]["value"] == (1,)
    assert updated.metadata["nested"]["value"] == (2,)
    assert not resource().with_updates(title="Title").has_value
    with pytest.raises(ValidationError):
        selected.with_updates(metadata={"session": object()})


def test_ids_preserve_ancestry_without_separator_collisions():
    assert make_resource_id("out", "a/b") != make_resource_id("out/a", "b")
    assert make_resource_id("out", "collection-1", "item", "data") != (
        make_resource_id("out", "collection-2", "item", "data")
    )
    assert make_resource_id("one", "item", "data") != make_resource_id(
        "two", "item", "data"
    )
    assert make_resource_id("測定", "ä/#") == make_resource_id("測定", "ä/#")


def test_capabilities_are_independent_and_scoped_snapshots():
    scope = {"return_type": "xarray.Dataset", "revision": [1]}
    capability = ResourceCapability(
        state="available",
        runtime="python",
        candidates=[ResourceAction(id="xarray", title="xarray Dataset")],
        scope=scope,
    )
    selected = resource(capabilities=ResourceCapabilities(opener=capability))
    scope["revision"][0] = 2
    assert selected.capabilities.opener.scope["revision"] == (1,)
    assert selected.capabilities.preview.state == "unknown"
    assert selected.capabilities.opener.candidates[0].id == "xarray"
    restored = JobResultResource.model_validate_json(selected.model_dump_json())
    assert restored.capabilities == selected.capabilities
    with pytest.raises(TypeError):
        capability.scope["return_type"] = "other"


@pytest.mark.parametrize(
    "snapshot, field, value",
    [
        (ResourceAction(id="reader", title="Reader"), "title", "Changed"),
        (ResourceCapabilities(), "opener", ResourceCapability()),
        (OutputDiscoveryState(), "discovery_state", "complete"),
        (ResourceDiagnostic(code="note", message="Original"), "message", "Changed"),
        (JobResultResourceListing(), "continuation", "changed"),
    ],
)
def test_supporting_snapshots_are_frozen(snapshot, field, value):
    with pytest.raises(ValidationError, match="frozen"):
        setattr(snapshot, field, value)


@pytest.mark.parametrize("state", ["available", "unavailable"])
def test_completed_assessments_require_runtime(state):
    with pytest.raises(ValidationError, match="requires a runtime"):
        ResourceCapability(state=state)


def test_available_assessment_requires_candidate():
    with pytest.raises(ValidationError, match="at least one candidate"):
        ResourceCapability(state="available", runtime="python")


def test_unknown_assessment_can_explain_failure():
    capability = ResourceCapability(reason="Assessment failed", runtime="python")
    assert capability.state == "unknown"
    assert capability.reason == "Assessment failed"


def test_listing_selection_iteration_and_indexing_are_local():
    one = resource()
    two = resource(item="item-2")
    three = resource(output="other")
    listing = JobResultResourceListing(
        resources=[one, two, three], discovery_state="partial", continuation="opaque"
    )
    with patch(
        "socket.create_connection", side_effect=AssertionError("Unexpected I/O")
    ):
        assert len(listing) == 3
        assert tuple(listing) == (one, two, three)
        assert listing[0] is one
        assert listing[-1] is three
        assert listing[1:] == (two, three)
        assert listing.select(id=one.id) is one
        assert (
            listing.select(output_name="dataset", item_id="item-2", key="data") is two
        )
        with pytest.raises(AmbiguousResourceError, match="3 loaded resources"):
            listing.select(key="data")
        with pytest.raises(AmbiguousResourceError):
            listing.select(item_id="item-1")
        with pytest.raises(ResourceNotFoundError, match="No loaded resource"):
            listing.select(key="missing")
        with pytest.raises(TypeError, match="Unsupported resource selection"):
            listing.select(href="anything")
        with pytest.raises(IndexError):
            listing[3]
    assert listing.continuation == "opaque"


def test_select_without_criteria_and_none_criteria():
    selected = resource(item_id=None)
    listing = JobResultResourceListing(resources=[selected])
    assert listing.select() is selected
    assert listing.select(item_id=None) is selected
    with pytest.raises(ResourceNotFoundError):
        JobResultResourceListing(discovery_state="complete").select()


def test_duplicate_ids_rejected_but_duplicate_keys_allowed():
    with pytest.raises(ValidationError, match="IDs must be unique"):
        JobResultResourceListing(resources=[resource(), resource()])
    assert (
        len(JobResultResourceListing(resources=[resource(), resource(item="item-2")]))
        == 2
    )


def test_empty_failed_outputs_and_partial_siblings_round_trip():
    diagnostic = ResourceDiagnostic(
        code="inaccessible", message="Metadata fetch failed"
    )
    states = {
        "dataset": OutputDiscoveryState(discovery_state="complete"),
        "empty": OutputDiscoveryState(discovery_state="complete"),
        "failed": OutputDiscoveryState(
            discovery_state="error", diagnostics=[diagnostic]
        ),
    }
    listing = JobResultResourceListing(
        resources=[resource()],
        discovery_state="partial",
        continuation="opaque",
        output_states=states,
        diagnostics=[
            ResourceDiagnostic(code="limit", message="Request budget reached")
        ],
    )
    states.clear()
    assert set(listing.output_states) == {"dataset", "empty", "failed"}
    assert (
        listing.output_states["failed"].diagnostics[0].message
        == "Metadata fetch failed"
    )
    with pytest.raises(TypeError):
        listing.output_states["new"] = OutputDiscoveryState()
    restored = JobResultResourceListing.model_validate_json(listing.model_dump_json())
    assert restored == listing
    assert restored.select(id=listing[0].id).id == listing[0].id
    assert restored.output_states["empty"].discovery_state == "complete"
    assert "job_results" not in listing.model_dump()


def test_original_output_stays_separate_from_selected_value():
    original = JobResults(root={"dataset": {"tables": {"first": [1], "second": [2]}}})
    selected = resource(
        kind="value",
        link=None,
        value=original.root["dataset"]["tables"]["first"],
        provenance={
            "job_id": "job-1",
            "output_value": original.model_dump(mode="json"),
        },
    )
    original.root["dataset"]["tables"]["first"].append(3)
    assert selected.value == (1,)
    assert selected.provenance["output_value"]["dataset"]["tables"]["first"] == (1,)
    assert "second" not in selected.model_dump(mode="json")["value"]


def test_rendering_includes_metadata_and_escapes_html():
    unsafe = '<script>alert("unsafe")</script>'
    diagnostic = ResourceDiagnostic(code="<failure>", message=unsafe)
    selected = resource(
        title=unsafe,
        roles=["data", "<metadata>"],
        discovery_state="error",
        diagnostics=[diagnostic],
        capabilities=ResourceCapabilities(
            opener=ResourceCapability(
                state="available",
                runtime="python",
                candidates=[ResourceAction(id="xarray", title="<xarray>")],
            ),
            preview=ResourceCapability(
                state="unavailable", runtime="browser", reason="No preview renderer"
            ),
        ),
    )
    listing = JobResultResourceListing(
        resources=[selected],
        discovery_state="partial",
        continuation="opaque",
        output_states={
            unsafe: OutputDiscoveryState(
                discovery_state="error", diagnostics=[diagnostic]
            )
        },
        diagnostics=[diagnostic],
    )
    with patch(
        "socket.create_connection", side_effect=AssertionError("Unexpected I/O")
    ):
        plain = str(listing)
        html = listing._repr_html_()
        assert repr(listing) == plain
        assert html == listing._repr_html_()
    for text in (
        "dataset/item-1/data",
        "application/zarr; version=2",
        "data,",
        "partial",
        "Another page",
    ):
        assert text in plain and text in html
    assert unsafe in plain
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;metadata&gt;" in html
    assert "&lt;xarray&gt;" in html
    assert "available" in html and "unavailable: No preview renderer" in html


@pytest.mark.parametrize("state", ["unresolved", "partial", "complete", "error"])
def test_empty_states_are_visible(state):
    listing = JobResultResourceListing(discovery_state=state)
    for rendered in (str(listing), listing._repr_html_()):
        assert f"Discovery: {state}" in rendered
        assert "loaded resources: 0" in rendered
        assert "No resources loaded" in rendered


def test_display_fallbacks_and_deferred_container():
    selected = resource(
        key=None, item_id=None, path="", media_type=None, kind="stac-catalog"
    )
    listing = JobResultResourceListing(resources=[selected], discovery_state="complete")
    assert selected.display_title == selected.id
    assert listing[0].discovery_state == "unresolved"
    for rendered in (str(listing), listing._repr_html_()):
        assert "unspecified" in rendered
        assert "unknown" in rendered
        assert "unresolved" in rendered
    assert resource().display_title == "data"
    assert resource(title="A title").display_title == "A title"
    assert "item-1" in str(JobResultResourceListing(resources=[resource(path="")]))
