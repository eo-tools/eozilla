#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from http import HTTPStatus
from typing import Optional

from fastapi import HTTPException

from gavicore.models import ApiError
from gavicore.service.errors import (
    ErrorTypeId,
    create_api_error,
    get_error_type_id,
)


class ServiceException(HTTPException):
    """Raised if a service error occurred."""

    content: ApiError

    def __init__(
        self,
        status_code: int,
        detail: str,
        exception: Optional[Exception] = None,
        type_id: ErrorTypeId | None = None,
        is_job_problem: bool = False,
    ):
        super().__init__(status_code=status_code, detail=detail)

        if type_id is None:
            type_id = get_error_type_id(
                status_code,
                is_job_problem=is_job_problem,
                default="internal-server-error",
            )

        title = str(exception) if exception else HTTPStatus(status_code).phrase

        self.content = create_api_error(
            type_id,
            status=status_code,
            title=title,
            detail=detail,
            exception=exception,
        )


class ServiceConfigException(ServiceException):
    """Raised if a service configuration error occurred."""

    def __init__(self, message: str):
        super().__init__(
            detail=message,
            status_code=500,
            type_id="internal-server-config-error",
            exception=self,
        )
