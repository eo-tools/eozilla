#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, Field


class OAParameter(BaseModel):
    name: str
    in_: Annotated[
        Literal["path", "query", "header", "cookie"], Field(default=None, alias="in")
    ]
    description: Annotated[str, Field(default=None)]
    required: bool = False
    schema_: Annotated[dict[str, Any], Field(default=None, alias="schema")]


class OAContent(BaseModel):
    schema_: Annotated[dict[str, Any], Field(default=None, alias="schema")]
    examples: Annotated[dict[str, Any], Field(default=None)]


class OARequestBody(BaseModel):
    description: Annotated[str, Field(default=None)]
    content: dict[str, OAContent]
    required: Annotated[bool, Field(default=False)]


class OAResponse(BaseModel):
    description: Annotated[str, Field(default=None)]
    content: Annotated[dict[str, OAContent], Field(default_factory=lambda: {})]


class OAMethod(BaseModel):
    tags: Annotated[list[str], Field(default=None)]
    summary: Annotated[str, Field(default=None)]
    description: Annotated[str, Field(default=None)]
    operationId: Annotated[str, Field(default=None)]
    parameters: Annotated[list[OAParameter], Field(default_factory=lambda: [])]
    requestBody: Annotated[OARequestBody, Field(default=None)]
    responses: Annotated[dict[str, OAResponse], Field(default_factory=lambda: {})]
    callbacks: Annotated[
        dict[str, dict[str, "OAEndpoint"]], Field(default_factory=lambda: {})
    ]


class OAEndpoint(BaseModel):
    options: Annotated[OAMethod, Field(default=None)]
    get: Annotated[OAMethod, Field(default=None)]
    put: Annotated[OAMethod, Field(default=None)]
    post: Annotated[OAMethod, Field(default=None)]
    delete: Annotated[OAMethod, Field(default=None)]


class OASchema(BaseModel):
    openapi: str
    info: Annotated[dict[str, Any], Field(default_factory=lambda: {})]
    servers: Annotated[list[dict[str, Any]], Field(default_factory=lambda: [])]
    paths: Annotated[dict[str, dict[str, OAMethod]], Field(default_factory=lambda: {})]
    components: Annotated[dict[str, Any], Field(default_factory=lambda: {})]


OAMethod.model_rebuild()


def load_openapi_schema(schema_path: Path) -> OASchema:
    with schema_path.open("rt") as stream:
        schema_dict = yaml.load(stream, Loader=yaml.SafeLoader)
    return OASchema.model_validate(schema_dict)
