#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging
import time
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .exceptions import ServiceException

app = FastAPI()


@app.exception_handler(ServiceException)
async def json_http_exception_handler(
    _request: Request, exc: ServiceException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content.model_dump(
            mode="json", exclude_defaults=False, exclude_none=True, exclude_unset=True
        ),
    )


@app.middleware("http")
async def log_request_duration(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start_time = time.perf_counter()

    # Process the request
    response = await call_next(request)

    # Calculate duration
    duration = time.perf_counter() - start_time

    # Log info (method, URL path, duration in ms)
    logger = logging.getLogger("uvicorn.request_duration")
    logger.debug(
        f"{request.method} {request.url.path} completed in {duration * 1000:.2f} ms"
    )

    return response
