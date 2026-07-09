#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pytest
import remotestate as rs

from cuiman.app.state import AppState, _create_defaults


def test_app_state():
    app_state = AppState()
    rs_store = app_state.store
    assert isinstance(rs_store, rs.Store)
    assert rs_store.get("processRequests") == {}

    changes = []

    import copy

    def record_changes(change):
        changes.append(copy.deepcopy(change))

    rs_store.subscribe(record_changes)

    rs_store.set("processRequests.generate_cube.inputs.date_range", [10, 20])
    rs_store.set("processRequests.generate_cube.inputs.bbox", [1, 2, 3, 4])
    rs_store.set(
        "processRequests.generate_cube.outputs.return_value", {"mediaType": "image/png"}
    )

    assert rs_store.get("processRequests") == {
        "generate_cube": {
            "inputs": {
                "bbox": [1, 2, 3, 4],
                "date_range": [10, 20],
            },
            "outputs": {
                "return_value": {"mediaType": "image/png"},
            },
        }
    }

    assert changes == [
        {("processRequests", "generate_cube", "inputs", "date_range"): [10, 20]},
        {("processRequests", "generate_cube", "inputs", "bbox"): [1, 2, 3, 4]},
        {
            ("processRequests", "generate_cube", "outputs", "return_value"): {
                "mediaType": "image/png"
            }
        },
    ]


def test_remote_store_with_subscripts():
    app_state = AppState()
    rs_store = app_state.store

    changes = []

    import copy

    def record_changes(change):
        changes.append(copy.deepcopy(change))

    rs_store.subscribe(record_changes)

    rs_store[
        "processRequests", "218", "inputs", "c30145a7-029c-4499-98bc-9903ca46531c"
    ] = "2026-06-01"
    rs_store.at["processRequests"]["218"]["inputs"][
        "472efeab-514a-4e15-9dba-d5812d653065"
    ] = "2026-06-07"
    # mixed
    rs_store.at.processRequests["218"].inputs[
        "bed1920e-51c0-406e-b22e-70d1f86d95d4"
    ] = "POLYGON (( 9.66 53.75,10.38 53.75,10.38 53.35, 9.66 53.35, 9.66 53.75))"

    assert changes == [
        {
            (
                "processRequests",
                "218",
                "inputs",
                "c30145a7-029c-4499-98bc-9903ca46531c",
            ): "2026-06-01"
        },
        {
            (
                "processRequests",
                "218",
                "inputs",
                "472efeab-514a-4e15-9dba-d5812d653065",
            ): "2026-06-07"
        },
        {
            (
                "processRequests",
                "218",
                "inputs",
                "bed1920e-51c0-406e-b22e-70d1f86d95d4",
            ): "POLYGON (( 9.66 53.75,10.38 53.75,10.38 53.35, 9.66 53.35, 9.66 53.75))"
        },
    ]


def test_create_defaults():
    assert _create_defaults(rs.path.parse_path("processRequests.generate_cube")) == {
        "inputs": {},
        "outputs": {},
    }
    assert (
        _create_defaults(rs.path.parse_path("processRequests.generate_cube.inputs"))
        == {}
    )
    assert (
        _create_defaults(rs.path.parse_path("processRequests.generate_cube.outputs"))
        == {}
    )


@pytest.mark.parametrize(
    "path",
    [
        "other",
        "processRequests",
        "processRequests.generate_cube.status",
    ],
)
def test_create_defaults_rejects_unsupported_paths(path):
    with pytest.raises(KeyError, match=path):
        _create_defaults(rs.path.parse_path(path))
