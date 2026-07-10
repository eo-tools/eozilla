#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pytest
import remotestate as rs
from remotestate import StoreAt

from gavicore.models import ProcessRequest, ResponseType

# noinspection PyProtectedMember
from cuiman.app.state import (
    AppState,
    _create_defaults,
    _normalize_process_request,
    _normalize_process_request_dicts,
    _normalize_process_requests,
)


def test_app_state_remote_store():
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


def test_remote_store_remote_store_with_subscripts():
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


def test_app_state_process_request_helpers():
    app_state = AppState()

    assert hasattr(app_state.process_requests, "value")
    assert hasattr(app_state.process_requests, "__getattr__")
    assert hasattr(app_state.process_requests, "__setattr__")

    assert app_state.store.get("processRequests") == {}
    assert app_state.at["processRequests"] is not None
    assert app_state.get_process_request("missing") is None

    app_state.set_process_request("from_model", ProcessRequest(inputs={"value": 1}))
    app_state.set_process_request(
        "from_dict",
        {"inputs": {"value": 2}, "response": ResponseType.document},
    )

    assert app_state.store.get("processRequests") == {
        "from_model": {"inputs": {"value": 1}},
        "from_dict": {"inputs": {"value": 2}, "response": "document"},
    }

    from_model = app_state.get_process_request("from_model")
    assert from_model is not None
    assert from_model.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 1}}

    from_dict = app_state.get_process_request("from_dict")
    assert from_dict is not None
    assert from_dict.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 2}, "response": "document"}

    app_state.process_requests = {
        "dict_input": {"inputs": {"value": 3}},
        "model_input": ProcessRequest(
            inputs={"value": 4},
            response=ResponseType.document,
        ),
    }

    assert app_state.store.get("processRequests") == {
        "dict_input": {"inputs": {"value": 3}},
        "model_input": {"inputs": {"value": 4}, "response": "document"},
    }
    dict_input = app_state.get_process_request("dict_input")
    assert dict_input is not None
    assert dict_input.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 3}}

    model_input = app_state.get_process_request("model_input")
    assert model_input is not None
    assert model_input.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 4}, "response": "document"}


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


def test_normalize_process_requests_and_reject_invalid_values():
    request = ProcessRequest(inputs={"value": 1}, response=ResponseType.document)

    normalized_requests = _normalize_process_requests(
        {
            "from_dict": {"inputs": {"value": 2}},
            "from_model": request,
        }
    )
    assert {
        key: value.model_dump(mode="json", exclude_defaults=True, exclude_none=True)
        for key, value in normalized_requests.items()
    } == {
        "from_dict": {"inputs": {"value": 2}},
        "from_model": {"inputs": {"value": 1}, "response": "document"},
    }

    assert _normalize_process_request_dicts(
        {
            "from_dict": {"inputs": {"value": 2}},
            "from_model": request,
        }
    ) == {
        "from_dict": {"inputs": {"value": 2}},
        "from_model": {"inputs": {"value": 1}, "response": "document"},
    }

    with pytest.raises(TypeError, match="request must be a ProcessRequest or dict"):
        _normalize_process_request(123)
