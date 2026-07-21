#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from typing import Final, Literal, TypeAlias, TypeGuard, get_args

from gavicore.models import ApiError
from gavicore.util.ensure import ensure_type

"""Helpers for resolving API problem types and building `ApiError` values."""

ErrorTypeId: TypeAlias = Literal[
    # OGC API - Processes Part 1 (Core)
    "no-such-process",
    "no-such-job",
    "result-not-ready",
    # OGC API - Processes Part 2 (DRU)
    "unsupported-media-type",
    "duplicated-process",
    "immutable-process",
    "workflow-not-found",
    # Eozilla
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
"""Type of an error type identifier."""

_DEFAULT_ERROR_URI_BASE = "https://eo-tools.github.io/eozilla/problems"

_OGC_ERROR_TYPE_URIS: Final[dict[ErrorTypeId, str]] = {
    # OGC API - Processes Part 1 (Core)
    "no-such-process": (
        "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process"
    ),
    "no-such-job": (
        "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-job"
    ),
    "result-not-ready": (
        "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/result-not-ready"
    ),
    # OGC API - Processes Part 2 (DRU)
    "unsupported-media-type": (
        "https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/unsupported-media-type"
    ),
    "duplicated-process": (
        "https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/duplicated-process"
    ),
    "immutable-process": (
        "https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/immutable-process"
    ),
    "workflow-not-found": (
        "https://www.opengis.net/def/exceptions/ogcapi-processes-2/1.0/workflow-not-found"
    ),
}

_HTTP_STATUS_CODE_TO_ERROR_TYPE_ID: Final[dict[int, ErrorTypeId]] = {
    400: "bad-request",
    401: "unauthorized",
    403: "forbidden",
    404: "no-such-process",
    409: "duplicated-process",
    413: "payload-too-large",
    415: "unsupported-media-type",
    429: "rate-limit-exceeded",
    500: "internal-server-error",
    501: "not-implemented",
}

_ERROR_ID_SET: set[str] = set(get_args(ErrorTypeId))


def is_error_type_id(value: str) -> TypeGuard[ErrorTypeId]:
    """Check whether a string is a supported API error type identifier.

    Args:
        value: The string to validate.

    Returns:
        `True` if `value` is one of the supported
        [`ErrorTypeId`][gavicore.service.errors.ErrorTypeId] values,
        otherwise `False`.
    """
    return value in _ERROR_ID_SET


def get_error_type_uri(type_id: ErrorTypeId) -> str:
    """Resolve an error type identifier to its canonical problem-type URI.

    OGC-defined problem types are mapped to their official OGC exception URIs.
    All remaining Eozilla-specific problem types are mapped to the Eozilla
    problem base URI with the error type identifier as fragment.

    Args:
        type_id: The error type identifier to resolve.

    Returns:
        The canonical URI representing the given error type.
    """
    if not is_error_type_id(type_id):
        raise ValueError(f"Unknown type_id: {type_id}")
    if type_id in _OGC_ERROR_TYPE_URIS:
        return _OGC_ERROR_TYPE_URIS[type_id]
    # See http://www.opengis.net/doc/IS/ogcapi-processes-1/1.0, section 7.13.3.,
    # Error Situations, Requirement 46
    return f"{_DEFAULT_ERROR_URI_BASE}#{type_id}"


def get_error_type_id(
    status_code: int,
    /,
    is_job_problem: bool = False,
    default: ErrorTypeId | None = None,
) -> ErrorTypeId:
    """Map an HTTP status code to a supported error type identifier.

    Known status codes are translated using the module's default mapping.
    If `is_job_problem` is set and the resolved error would be
    `"no-such-process"`, the returned type is adjusted to `"no-such-job"`.
    Unknown status codes fall back to `default` or, if no default is given,
    to `"internal-server-error"`.

    Args:
        status_code: The HTTP status code to translate.
        is_job_problem: Whether a `404` error should be interpreted as a
            missing job instead of a missing process.
        default: The fallback error type identifier for unmapped status codes.

    Returns:
        The resolved error type identifier.
    """
    if status_code in _HTTP_STATUS_CODE_TO_ERROR_TYPE_ID:
        type_id = _HTTP_STATUS_CODE_TO_ERROR_TYPE_ID[status_code]
        return (
            "no-such-job"
            if type_id == "no-such-process" and is_job_problem
            else type_id
        )
    else:
        return "internal-server-error" if default is None else default


def create_api_error(
    type_id: ErrorTypeId,
    /,
    exception: BaseException | None = None,
    instance: str | None = None,
    status: int | None = None,
    title: str | None = None,
    detail: str | None = None,
    traceback: str | list[str] | None = None,
) -> ApiError:
    """Create an `ApiError` from a problem type identifier and error details.

    If `exception` is provided, the error title defaults to `str(exception)`
    and the traceback defaults to the formatted traceback of that exception.
    Explicit `title` and `traceback` values take precedence over these
    derived defaults.

    Args:
        type_id: The problem type identifier used to resolve the error URI.
        exception: The underlying exception that caused the problem.
        instance: An optional URI identifying the specific problem instance.
        status: The related HTTP status code.
        title: A short human-readable problem summary.
        detail: A detailed human-readable problem description.
        traceback: An optional server-side traceback string or list of lines.

    Returns:
        The constructed [`ApiError`][gavicore.models.ApiError] instance.
    """
    ensure_type("type_id", type_id, str)
    if not is_error_type_id(type_id):
        raise ValueError(f"Invalid type_id: {type_id}")

    if exception is not None:
        import traceback as tb

        ensure_type("exc", exception, BaseException)
        title = title or str(exception)
        traceback = traceback or tb.format_exception(exception)

    return ApiError(
        type=get_error_type_uri(type_id),
        status=status,
        title=title,
        detail=detail,
        instance=instance,
        **({"x-traceback": traceback} if traceback else {}),
    )
