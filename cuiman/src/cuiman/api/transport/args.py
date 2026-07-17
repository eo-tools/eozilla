#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import pydantic
import uri_template
from pydantic import BaseModel

from cuiman.api.exceptions import ClientError
from gavicore.models import ApiError


CLIENT_ERROR_URI: Final[str] = (
    "https://eo-tools.github.io/eozilla/cuiman/api/#cuiman.ClientError"
)


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

    def __post_init__(self):
        if not uri_template.validate(self.path):
            raise ValueError(f"Invalid URI template {self.path}")

    def get_url(self, api_url: str) -> str:
        endpoint_path = uri_template.expand(self.path, **self.path_params)
        if endpoint_path is None:
            raise RuntimeError(
                f"URI template expansion failed for {self.path}, {self.path_params}"
            )
        return f"{api_url.rstrip('/')}/{endpoint_path.lstrip('/')}"

    def get_json_for_request(self) -> Any:
        request = self.request
        return (
            request.model_dump(
                mode="json", by_alias=True, exclude_none=True, exclude_defaults=True
            )
            if isinstance(request, BaseModel)
            else request
        )

    def get_response_for_status(
        self, status_code: int, json_data: Any, return_type_map: dict[type, type]
    ):
        status_key = str(status_code)
        return_type = self.return_types.get(status_key)
        if return_type is not None:
            return_type = return_type_map.get(return_type, return_type)
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
        self, status_code: int, json_data: Any, message: str
    ) -> ClientError:
        status_key = str(status_code)
        # Currently, all error types fall back to ApiError
        _return_type = self.error_types.get(status_key)
        if isinstance(json_data, dict):
            try:
                api_error = ApiError(**json_data)
            except pydantic.ValidationError as e:
                api_error = ApiError(
                    type=CLIENT_ERROR_URI,
                    status=status_code,
                    title="Received invalid error description from API",
                    detail=(
                        f"Expected RFC7807-compliant error description, "
                        f"but parsing received data produced an error:\n{e}"
                    ),
                )
        else:
            api_error = ApiError(
                type=CLIENT_ERROR_URI,
                status=status_code,
                title="Missing error description from API",
                detail=(
                    f"Expected RFC7807-compliant error description, "
                    f"but received data:\n{json.dumps(json_data)}"
                ),
            )
        return ClientError(f"{message} (status {status_code})", api_error=api_error)
