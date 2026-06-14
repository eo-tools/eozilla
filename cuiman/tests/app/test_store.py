#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import remotestate as rs

from cuiman.app.store import create_remote_store


def test_remote_store():
    rs_store = create_remote_store()
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
        {
            "processRequests": {
                "generate_cube": {"inputs": {"date_range": [10, 20]}, "outputs": {}}
            },
            "processRequests.generate_cube": {
                "inputs": {"date_range": [10, 20]},
                "outputs": {},
            },
            "processRequests.generate_cube.inputs": {"date_range": [10, 20]},
            "processRequests.generate_cube.inputs.date_range": [10, 20],
        },
        {
            "processRequests": {
                "generate_cube": {
                    "inputs": {"bbox": [1, 2, 3, 4], "date_range": [10, 20]},
                    "outputs": {},
                }
            },
            "processRequests.generate_cube": {
                "inputs": {"bbox": [1, 2, 3, 4], "date_range": [10, 20]},
                "outputs": {},
            },
            "processRequests.generate_cube.inputs": {
                "bbox": [1, 2, 3, 4],
                "date_range": [10, 20],
            },
            "processRequests.generate_cube.inputs.bbox": [1, 2, 3, 4],
        },
        {
            "processRequests": {
                "generate_cube": {
                    "inputs": {"bbox": [1, 2, 3, 4], "date_range": [10, 20]},
                    "outputs": {"return_value": {"mediaType": "image/png"}},
                }
            },
            "processRequests.generate_cube": {
                "inputs": {"bbox": [1, 2, 3, 4], "date_range": [10, 20]},
                "outputs": {"return_value": {"mediaType": "image/png"}},
            },
            "processRequests.generate_cube.outputs": {
                "return_value": {"mediaType": "image/png"}
            },
            "processRequests.generate_cube.outputs.return_value": {
                "mediaType": "image/png"
            },
        },
    ]
