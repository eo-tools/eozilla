#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

import remotestate as rs

PROCESS_REQUESTS_KEY = "processRequests"


def create_app_remote_store() -> rs.Store:
    return rs.Store(
        {
            PROCESS_REQUESTS_KEY: {},
        },
        default_factory=_create_defaults,
    )


def _create_defaults(path: rs.path.Path) -> Any:
    if path[0] == rs.path.Property(PROCESS_REQUESTS_KEY):
        if len(path) == 2:
            # If e.g., path == "processRequests.generate_cube"
            return dict(inputs={}, outputs={})
        if len(path) == 3 and path[2] in (
            rs.path.Property("inputs"),
            rs.path.Property("outputs"),
        ):
            # If e.g., path == "processRequests.generate_cube.inputs"
            return {}
    raise KeyError(rs.path.format_path(path))
