#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import remotestate as rs

from gavicore.models import ProcessRequest

PROCESS_REQUESTS_KEY = "processRequests"

ProcessRequestInput = ProcessRequest | dict[str, Any]


class AppState:
    def __init__(self) -> None:
        self._store = rs.Store(
            {
                PROCESS_REQUESTS_KEY: {},
            },
            default_factory=_create_defaults,
        )

    @property
    def store(self) -> rs.Store:
        return self._store

    @property
    def at(self):
        return self._store.at

    @property
    def process_requests(self) -> Any:
        return self._store.at[PROCESS_REQUESTS_KEY]

    @process_requests.setter
    def process_requests(self, process_requests: dict[str, ProcessRequestInput]):
        request_dicts = _normalize_process_request_dicts(process_requests)
        self._store.set([PROCESS_REQUESTS_KEY], request_dicts)

    def get_process_request(self, process_id: str) -> ProcessRequest | None:
        process_requests = self._store.get(PROCESS_REQUESTS_KEY)
        assert isinstance(process_requests, dict)
        process_request = process_requests.get(process_id)
        if process_request is None:
            return None
        return _normalize_process_request(process_request)

    def set_process_request(
        self, process_id: str, process_request: ProcessRequestInput
    ):
        request_dict = _normalize_process_request_dict(process_request)
        self._store.at[PROCESS_REQUESTS_KEY][process_id] = request_dict


def _normalize_process_requests(
    process_requests: dict[str, ProcessRequestInput],
) -> dict[str, ProcessRequest]:
    return {k: _normalize_process_request(v) for k, v in process_requests.items()}


def _normalize_process_request_dicts(
    process_requests: dict[str, ProcessRequestInput],
) -> dict[str, dict[str, Any]]:
    return {k: _normalize_process_request_dict(v) for k, v in process_requests.items()}


def _normalize_process_request(process_request: ProcessRequestInput):
    if isinstance(process_request, ProcessRequest):
        return process_request
    if isinstance(process_request, dict):
        return ProcessRequest(**process_request)
    raise TypeError("request must be a ProcessRequest or dict")


def _normalize_process_request_dict(
    process_request: ProcessRequestInput,
) -> dict[str, Any]:
    request_obj = _normalize_process_request(process_request)
    return request_obj.model_dump(mode="json", exclude_defaults=True, exclude_none=True)


def _create_defaults(path: rs.path.Path) -> Any:
    if path[0] == PROCESS_REQUESTS_KEY:
        if len(path) == 2:
            # If e.g., path == "processRequests.generate_cube"
            return dict(inputs={}, outputs={})
        if len(path) == 3 and path[2] in ("inputs", "outputs"):
            # If e.g., path == "processRequests.generate_cube.inputs"
            return {}
    raise KeyError(rs.path.format_path(path))
