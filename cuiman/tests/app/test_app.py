#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

import pytest
import remotestate as rs

import cuiman.app.app as app_module
from cuiman.app import App
from cuiman.app.app import (
    PROCESS_REQUESTS_KEY,
    _create_defaults,
    _normalize_process_request,
    _normalize_process_request_dict,
    _normalize_process_request_dicts,
    _normalize_process_requests,
)
from gavicore.models import ProcessRequest, ResponseType


def test_create_remote_store_and_defaults():
    store = App.create_remote_store()

    assert isinstance(store, rs.Store)
    assert store.get(PROCESS_REQUESTS_KEY) == {}

    store.set("processRequests.generate_cube.inputs.date_range", [10, 20])
    store.set("processRequests.generate_cube.inputs.bbox", [1, 2, 3, 4])
    store.set(
        "processRequests.generate_cube.outputs.return_value",
        {"mediaType": "image/png"},
    )

    assert store.get(PROCESS_REQUESTS_KEY) == {
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


def test_app_accessors_and_process_request_roundtrip(monkeypatch):
    monkeypatch.setattr(app_module, "ensure_type", lambda *args, **kwargs: None)

    store = App.create_remote_store()
    serve_result = object()
    app = App(store, serve_result)

    assert app.remote_store is store
    assert app.serve_result is serve_result
    assert app.at["processRequests"] is not None
    assert app.process_requests.value == {}

    app.process_requests = {
        "from_dict": {"inputs": {"value": 1}},
        "from_model": ProcessRequest(
            inputs={"value": 2},
            response=ResponseType.document,
        ),
    }
    app.set_process_request(
        "set_from_dict",
        {"inputs": {"value": 3}, "response": "document"},
    )
    app.set_process_request(
        "set_from_model",
        ProcessRequest(inputs={"value": 4}, response=ResponseType.document),
    )

    assert app.process_requests.value == {
        "from_dict": {"inputs": {"value": 1}},
        "from_model": {"inputs": {"value": 2}, "response": "document"},
        "set_from_dict": {"inputs": {"value": 3}, "response": "document"},
        "set_from_model": {"inputs": {"value": 4}, "response": "document"},
    }

    assert app.get_process_request("missing") is None

    from_dict = app.get_process_request("from_dict")
    assert from_dict is not None
    assert from_dict.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 1}}

    from_model = app.get_process_request("from_model")
    assert from_model is not None
    assert from_model.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 2}, "response": "document"}

    set_from_dict = app.get_process_request("set_from_dict")
    assert set_from_dict is not None
    assert set_from_dict.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 3}, "response": "document"}

    set_from_model = app.get_process_request("set_from_model")
    assert set_from_model is not None
    assert set_from_model.model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 4}, "response": "document"}


def test_normalization_helpers_handle_models_and_dicts():
    request = ProcessRequest(inputs={"value": 1}, response=ResponseType.document)
    request_dict = {"inputs": {"value": 2}, "response": "document"}

    assert _normalize_process_request(request) is request
    assert _normalize_process_request(request_dict).model_dump(
        mode="json", exclude_defaults=True, exclude_none=True
    ) == {"inputs": {"value": 2}, "response": "document"}

    assert _normalize_process_request_dict(request) == {
        "inputs": {"value": 1},
        "response": "document",
    }
    assert _normalize_process_request_dict(request_dict) == {
        "inputs": {"value": 2},
        "response": "document",
    }

    normalized_requests = _normalize_process_requests(
        {
            "from_dict": request_dict,
            "from_model": request,
        }
    )
    assert {
        key: value.model_dump(mode="json", exclude_defaults=True, exclude_none=True)
        for key, value in normalized_requests.items()
    } == {
        "from_dict": {"inputs": {"value": 2}, "response": "document"},
        "from_model": {"inputs": {"value": 1}, "response": "document"},
    }

    assert _normalize_process_request_dicts(
        {
            "from_dict": request_dict,
            "from_model": request,
        }
    ) == {
        "from_dict": {"inputs": {"value": 2}, "response": "document"},
        "from_model": {"inputs": {"value": 1}, "response": "document"},
    }


def test_normalize_process_request_rejects_invalid_values():
    with pytest.raises(TypeError, match="request must be a ProcessRequest or dict"):
        _normalize_process_request(123)  # type: ignore[arg-type]
