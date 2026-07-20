#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Final, Literal, TypeAlias, TypeGuard, get_args

from gavicore.models import ApiError
from gavicore.util.ensure import ensure_type

ErrorTypeId: TypeAlias = Literal[
    "no-such-process",
    "no-such-job",
    "result-not-ready",
    "bad-request",
    "invalid-parameter",
    "invalid-parameter-value",
    "missing-parameter",
    "invalid-header-value",
    "unsupported-media-type",
    "unauthorized",
    "forbidden",
    "conflict",
    "payload-too-large",
    "rate-limit-exceeded",
    "not-implemented",
    "internal-server-error",
    "internal-server-config-error",
]

_ERROR_ID_SET: set[str] = set(get_args(ErrorTypeId))


_DEFAULT_ERROR_URI_BASE = "https://eo-tools.github.io/eozilla/problems/#"

_OGC_ERROR_TYPE_URIS: Final[dict[ErrorTypeId, str]] = {
    # OGC API - Processes Part 1
    "no-such-process": (
        "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process"
    ),
    "no-such-job": (
        "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-job"
    ),
    "result-not-ready": (
        "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/result-not-ready"
    ),
    # Eozilla-defined problem types
    "bad-request": f"{_DEFAULT_ERROR_URI_BASE}/#bad-request",
    "invalid-parameter": f"{_DEFAULT_ERROR_URI_BASE}/#invalid-parameter",
    "invalid-parameter-value": f"{_DEFAULT_ERROR_URI_BASE}/#invalid-parameter-value",
    "missing-parameter": f"{_DEFAULT_ERROR_URI_BASE}/#missing-parameter",
    "invalid-header-value": f"{_DEFAULT_ERROR_URI_BASE}/#invalid-header-value",
    "unsupported-media-type": f"{_DEFAULT_ERROR_URI_BASE}/#unsupported-media-type",
    "unauthorized": f"{_DEFAULT_ERROR_URI_BASE}/#unauthorized",
    "forbidden": f"{_DEFAULT_ERROR_URI_BASE}/#forbidden",
    "conflict": f"{_DEFAULT_ERROR_URI_BASE}/#conflict",
    "payload-too-large": f"{_DEFAULT_ERROR_URI_BASE}/#payload-too-large",
    "rate-limit-exceeded": f"{_DEFAULT_ERROR_URI_BASE}/#rate-limit-exceeded",
    "not-implemented": f"{_DEFAULT_ERROR_URI_BASE}/#not-implemented",
    "internal-server-error": f"{_DEFAULT_ERROR_URI_BASE}/#internal-server-error",
    "internal-server-config-error": (
        f"{_DEFAULT_ERROR_URI_BASE}/#internal-server-config-error"
    ),
}


def is_error_type_id(value: str) -> TypeGuard[ErrorTypeId]:
    return value in _ERROR_ID_SET


def get_error_type_uri(type_id: ErrorTypeId) -> str:
    if not is_error_type_id(type_id):
        raise ValueError(f"Unknown type_id: {type_id}")
    if type_id not in _OGC_ERROR_TYPE_URIS:
        return _OGC_ERROR_TYPE_URIS[type_id]
    return f"{_DEFAULT_ERROR_URI_BASE}/#{type_id}"


def create_api_error(
    type_id: str,
    exc: BaseException | None = None,
    instance: str | None = None,
    status: int | None = None,
    title: str | None = None,
    detail: str | None = None,
    traceback: str | list[str] | None = None,
) -> ApiError:
    ensure_type("type_id", type_id, str)
    assert type_id is not None
    if not is_error_type_id(type_id):
        raise ValueError(f"Invalid type_id: {type_id}")

    if exc is not None:
        import traceback as tb

        ensure_type("exc", exc, BaseException)
        title = title or str(exc)
        traceback = traceback or tb.format_exception(exc)

    return ApiError(
        type=get_error_type_uri(type_id),
        status=status,
        title=title,
        detail=detail,
        instance=instance,
        **({"x-traceback": traceback} if traceback else {}),
    )
