#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException

from gavicore.models import ApiError

DEFAULT_API_ERROR_URI = (
    "https://eo-tools.github.io/eozilla/wraptile/api/exceptions/#ServiceException"
)


class ServiceException(HTTPException):
    """Raised if a service error occurred."""

    content: ApiError

    def __init__(
        self,
        status_code: int,
        detail: str,
        exception: Optional[Exception] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        title = HTTPStatus(status_code).phrase
        if exception is not None:
            api_error = ApiError.from_exception(
                exception,
                status=status_code,
                title=title,
                detail=detail,
            )
        else:
            api_error = ApiError(
                type=DEFAULT_API_ERROR_URI,
                status=status_code,
                title=title,
                detail=detail,
            )
        self.content = api_error


class ServiceConfigException(ServiceException):
    """Raised if a service configuration error occurred."""

    def __init__(self, message: str):
        super().__init__(status_code=500, detail=message, exception=self)
