#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from urllib.parse import urljoin

import pydantic
import uri_template
from pydantic import BaseModel

from s2gos_client.api.exceptions import ClientError
from s2gos_common.models import ApiError


@dataclass
class TransportArgs:
    path: str
    method: Literal["get", "post", "put", "delete"] = "get"
    path_params: dict[str, Any] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    request: BaseModel | None = None
    return_types: dict[str, type | None] = field(default_factory=dict)
    error_types: dict[str, type | None] = field(default_factory=dict)
    extra_kwargs: dict[str, Any] = field(default_factory=dict)

    def get_url(self, server_url: str) -> str:
        return urljoin(server_url, uri_template.expand(self.path, **self.path_params))

    def get_json_for_request(self) -> Any:
        request = self.request
        return (
            request.model_dump(
                mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
            )
            if isinstance(request, BaseModel)
            else request
        )

    def get_response_for_status(self, status_code: int, json_data: Any):
        status_key = str(status_code)
        return_type = self.return_types.get(status_key)
        if (
            return_type is not None
            and inspect.isclass(return_type)
            and issubclass(return_type, BaseModel)
        ):
            return return_type.model_validate(json_data)
        else:
            # TODO: warn or raise if we miss return_type
            return json_data

    # noinspection PyMethodMayBeStatic
    def get_exception_for_status(
        self,
        status_code: int,
        message: str,
        json_data: Optional[Any] = None,
    ) -> ClientError:
        status_key = str(status_code)
        # Currently, all error types fall back to ApiError
        _return_type = self.error_types.get(status_key)
        if isinstance(json_data, dict):
            try:
                api_error = ApiError(**json_data)
            except pydantic.ValidationError as e:
                api_error = ApiError(
                    type="ValidationError",
                    title="Received invalid error details from API",
                    detail=f"{e}",
                )
        else:
            api_error = ApiError(
                type="ValidationError",
                title="Missing error details from API",
                detail=f"JSON object expected, but got {type(json_data).__name__}",
            )
        return ClientError(f"{message} (status {status_code})", api_error=api_error)
