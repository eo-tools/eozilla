#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from typing import Any

import remotestate as rs

from gavicore.models import ProcessRequest
from gavicore.util.ensure import ensure_type

PROCESS_REQUESTS_KEY = "processRequests"

ProcessRequestInput = ProcessRequest | dict[str, Any]


class App:
    """The app instance displayed and returned by `Client.show_app()`.
    It allows for convenient interaction with the app's data state,
    """

    def __init__(self, remote_store: rs.Store, serve_result: rs.ServeResult) -> None:
        ensure_type("remote_store", remote_store, rs.Store)
        ensure_type("serve_result", serve_result, rs.ServeResult)
        self._serve_result = serve_result
        self._remote_store = remote_store

    @property
    def remote_store(self) -> rs.Store:
        """The app's remote store."""
        return self._remote_store

    @property
    def serve_result(self) -> rs.ServeResult:
        """The result from `remotestate.serve()`."""
        return self._serve_result

    @classmethod
    def create_remote_store(cls) -> rs.Store:
        """Create a new `remotestate.Store` instance for an app instance."""
        return rs.Store(
            {
                PROCESS_REQUESTS_KEY: {},
            },
            default_factory=_create_defaults,
        )

    @property
    def at(self) -> rs.StoreAt:
        """The underlying `remotestore.StoreAt` instance which provides access
        to the state data via keys, indexes, and attributes.
        """
        return self._remote_store.at

    @property
    def process_requests(self) -> rs.StoreAt:
        """The `remotestore.StoreAt` instance that accesses
        the app's current process requests.
        """
        return self._remote_store.at[PROCESS_REQUESTS_KEY]

    @process_requests.setter
    def process_requests(
        self, process_requests: dict[str, ProcessRequestInput]
    ) -> None:
        """Allows for changing the app's current process requests."""
        request_dicts = _normalize_process_request_dicts(process_requests)
        self._remote_store.set([PROCESS_REQUESTS_KEY], request_dicts)

    def get_process_request(self, process_id: str) -> ProcessRequest | None:
        """Get a process request."""
        process_requests = self._remote_store.get(PROCESS_REQUESTS_KEY)
        assert isinstance(process_requests, dict)
        process_request = process_requests.get(process_id)
        if process_request is None:
            return None
        return _normalize_process_request(process_request)

    def set_process_request(
        self, process_id: str, process_request: ProcessRequestInput
    ) -> None:
        """Set a process request."""
        request_dict = _normalize_process_request_dict(process_request)
        self._remote_store.at[PROCESS_REQUESTS_KEY][process_id] = request_dict


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
