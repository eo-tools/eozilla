import fastapi

from gavicore.dru_models import OGCApplicationPackage
from gavicore.dru_service import DRUService
from gavicore.models import ApiError, ProcessSummary

from .ogcapppkg_response import OgcApplicationPackageResponse
from .provider import get_service

dru_router = fastapi.APIRouter()


# noinspection PyPep8Naming
@dru_router.post(
    "/processes",
    response_model=ProcessSummary,
    status_code=201,
    responses={
        "202": {},
        "403": {"model": ApiError},
        "409": {"model": ApiError},
        "415": {"model": ApiError},
        "501": {"model": ApiError},
    },
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/cwl": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": True,
                    }
                },
                "application/cwl+json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": True,
                    }
                },
                "application/cwl+yaml": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": True,
                    }
                },
            },
            "required": True,
        }
    },
)
async def deploy_process(
    request: fastapi.Request,
    response: fastapi.Response,
    w: str | None = None,
    service: DRUService = fastapi.Depends(get_service),  # noqa B008
):
    return await service.deploy_process(
        w=w,
        request=request,
        response=response,
    )


# noinspection PyPep8Naming
@dru_router.put(
    "/processes/{processID}",
    response_model=ProcessSummary,
    responses={
        "201": {"model": ProcessSummary},
        "202": {"model": ProcessSummary},
        "204": {},
        "403": {"model": ApiError},
        "404": {"model": ApiError},
        "415": {"model": ApiError},
        # NOTE: use 501 for parts of the standard that are not implemented (yet)
        "501": {"model": ApiError},
    },
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/cwl": {"schema": ProcessSummary.model_json_schema()},
                "application/cwl+json": {"schema": ProcessSummary.model_json_schema()},
                "application/cwl+yaml": {"schema": ProcessSummary.model_json_schema()},
            },
            "required": True,
        }
    },
)
async def replace_process(
    processID: str,
    request: fastapi.Request,
    response: fastapi.Response,
    w: str | None = None,
    service: DRUService = fastapi.Depends(get_service),  # noqa B008
):
    return await service.replace_process(
        process_id=processID,
        w=w,
        request=request,
        response=response,
    )


# noinspection PyPep8Naming
@dru_router.delete(
    "/processes/{processID}",
    status_code=204,
    responses={
        "403": {"model": ApiError},
        "404": {"model": ApiError},
        "501": {"model": ApiError},
    },
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def undeploy_process(
    processID: str,
    request: fastapi.Request,
    response: fastapi.Response,
    service: DRUService = fastapi.Depends(get_service),  # noqa B008
):
    return await service.undeploy_process(
        process_id=processID, request=request, response=response
    )


# noinspection PyPep8Naming
@dru_router.get(
    "/processes/{processID}/package",
    response_model=OGCApplicationPackage,
    response_class=OgcApplicationPackageResponse,
    responses={
        "403": {"model": ApiError},
        "404": {"model": ApiError},
        "501": {"model": ApiError},
    },
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def get_formal_description(
    processID: str,
    request: fastapi.Request,
    response: fastapi.Response,
    service: DRUService = fastapi.Depends(get_service),  # noqa B008
):
    return await service.get_formal_description(
        process_id=processID, request=request, response=response
    )
