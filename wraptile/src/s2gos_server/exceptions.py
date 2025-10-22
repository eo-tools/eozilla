#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import traceback
from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException

from s2gos_common.models import ApiError


class ServiceException(HTTPException):
    """Raised if a service error occurred."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        exception: Optional[Exception] = None,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.content = ApiError(
            type=type(exception).__name__ if exception is not None else "ApiError",
            status=status_code,
            title=HTTPStatus(status_code).phrase,
            detail=detail,
            traceback=(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
                if exception is not None
                else None
            ),
        )


class ServiceConfigException(ServiceException):
    """Raised if a service configuration error occurred."""

    def __init__(self, message: str):
        super().__init__(status_code=500, detail=message, exception=self)
