#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal, TypeAlias

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field, RootModel

# ---------------------------------------------------------------------
#    JSONSchema
# ---------------------------------------------------------------------


class DataType(Enum):
    """The data type of a value to be validated by the [Schema][Schema]."""

    boolean = "boolean"
    integer = "integer"
    number = "number"
    string = "string"
    array = "array"
    object = "object"


class Schema(BaseModel):
    """Representation of the OpenAPI 3.0 Schema.

    The OpenAPI 3.0 Schema is a subset of JSON Schema draft-05
    with some noticeable extensions.

    Most importantly,

    - `type` is not allowed to be an array of types, and
      it is not allowed to be `"null"`. To indicate a value that can
      be `None`, `nullable=True` is used to allow a value to be `None`,
      instead of `type=["string", "null"]` in JSON Schema.
    - `items` must a schema, which means _tuples_ are not supported.
      (tuple = a schema of type "array" with fixed-length `items` being an
      array of possibly distinct schemas.

    Keywords and constructs that do not exist in JSON Schema:

        - `nullable = True`
        - `deprecated == True`
        - `readOnly = True`
        - `writeOnly = True`
        - `discriminator`
        - `xml`
        - `example`

    Keywords and constructs that are supported in JSON Schema,
    but not in OpenAPI 3.0 Schema:

        - `const`
        - `if` / `then` / `else`
        - `contains`
        - `patternProperties`
        - `dependencies`

    Note that OpenAPI Schemas are extendable;
    application-specific fields are usually prefixed
    by `"x-"`. For example, `x-ui` or `x-ui:widget`.
    """

    model_config = ConfigDict(
        # allow for extensions usually prefixed by "x-", e.g., "x-ui"
        extra="allow",
    )

    # general
    type: DataType | None = None
    title: str | None = None
    description: str | None = None
    enum: list | None = Field(None, min_length=1)
    default: Any | None = None
    nullable: bool | None = False
    readOnly: bool | None = False
    writeOnly: bool | None = False
    example: Any | None = None
    examples: Any | None = None
    deprecated: bool | None = False
    field_ref: str | None = Field(None, alias="$ref")
    # type "number" and "integer"
    minimum: int | float | None = None
    maximum: int | float | None = None
    exclusiveMinimum: bool | None = False
    exclusiveMaximum: bool | None = False
    multipleOf: float | None = Field(None, gt=0.0)
    # type "string"
    minLength: int | None = Field(0, ge=0)
    maxLength: int | None = Field(None, ge=0)
    format: str | None = None
    pattern: str | None = None
    contentMediaType: str | None = None
    contentEncoding: str | None = None
    contentSchema: str | None = None
    # type "array"
    items: Schema | None = None
    minItems: int | None = Field(0, ge=0)
    maxItems: int | None = Field(None, ge=0)
    uniqueItems: bool | None = False
    # type "object"
    properties: dict[str, Schema] | None = None
    required: list[str] | None = Field(None, min_length=1)
    minProperties: int | None = Field(0, ge=0)
    maxProperties: int | None = Field(None, ge=0)
    additionalProperties: Schema | bool | None = True
    # operators
    not_: Schema | None = Field(None, alias="not")
    allOf: list[Schema] | None = None
    oneOf: list[Schema] | None = None
    anyOf: list[Schema] | None = None
    discriminator: Discriminator | None = None


class Discriminator(BaseModel):
    propertyName: str | None = Field(None, min_length=1)
    mapping: dict[str, Schema] | None = None


# ---------------------------------------------------------------------
#    Common
# ---------------------------------------------------------------------


class Link(BaseModel):
    href: str
    rel: str | None = Field(None, examples=["service"])
    type: str | None = Field(None, examples=["application/json"])
    hreflang: str | None = Field(None, examples=["en"])
    title: str | None = None


# ---------------------------------------------------------------------
#    Service
# ---------------------------------------------------------------------


class Capabilities(BaseModel):
    title: str | None = Field(None, examples=["Example processing server"])
    description: str | None = Field(
        None,
        examples=["Example server implementing the OGC API - Processes 1.0 Standard"],
    )
    links: list[Link]


class ConformanceDeclaration(BaseModel):
    conformsTo: list[str]


class CRS(Enum):
    CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    CRS84H = "http://www.opengis.net/def/crs/OGC/0/CRS84h"


class Bbox(BaseModel):
    bbox: list[float] = Field(..., max_length=4, min_length=4)
    crs: CRS | None = CRS.CRS84


InlineValue: TypeAlias = (
    Any
    | bool
    | bytes
    | AnyUrl
    | date
    | AwareDatetime
    | str
    | int
    | float
    | list
    | dict[str, Any]
    | Bbox
)


class Metadata(BaseModel):
    title: str | None = None
    role: str | None = None
    href: str | None = None


class AdditionalParameter(BaseModel):
    name: str
    value: list[str | float | int | list[dict[str, Any]] | dict[str, Any]]


class AdditionalParameters(Metadata):
    parameters: list[AdditionalParameter] | None = None


class DescriptionType(BaseModel):
    model_config = ConfigDict(
        # allow for extensions usually prefixed by "x-", e.g., "x-ui"
        extra="allow",
    )

    title: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    metadata: list[Metadata] | None = None
    additionalParameters: AdditionalParameters | None = None


class Format(BaseModel):
    mediaType: str | None = None
    encoding: str | None = None
    schema_: AnyUrl | Schema | None = Field(None, alias="schema")


# ---------------------------------------------------------------------
#    Process
# ---------------------------------------------------------------------


class InputDescription(DescriptionType):
    minOccurs: int | None = 1
    maxOccurs: int | Literal["unbounded"] | None = None
    schema_: Schema = Field(..., alias="schema")


class OutputDescription(DescriptionType):
    schema_: Schema = Field(..., alias="schema")


class TransmissionMode(Enum):
    value = "value"
    reference = "reference"


class ProcessSummary(DescriptionType):
    id: str
    version: str
    jobControlOptions: list[JobControlOptions] | None = None
    outputTransmission: list[TransmissionMode] | None = None
    links: list[Link] | None = None


class ProcessList(BaseModel):
    processes: list[ProcessSummary]
    links: list[Link]


class ProcessDescription(ProcessSummary):
    inputs: dict[str, InputDescription] | None = None
    outputs: dict[str, OutputDescription] | None = None


class Output(BaseModel):
    format: Format | None = None
    transmissionMode: TransmissionMode | None = TransmissionMode.value


class ResponseType(Enum):
    raw = "raw"
    document = "document"


class Subscriber(BaseModel):
    """
    Optional URIs for callbacks for this job.

    Support for this parameter is not required and the parameter may be
    removed from the API definition, if conformance class **'callback'**
    is not listed in the conformance declaration under `/conformance`.
    """

    successUri: AnyUrl | None = None
    inProgressUri: AnyUrl | None = None
    failedUri: AnyUrl | None = None


class ProcessRequest(BaseModel):
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Output] | None = None
    response: ResponseType | None = ResponseType.raw
    subscriber: Subscriber | None = None


# ---------------------------------------------------------------------
#    Job
# ---------------------------------------------------------------------


class JobStatus(Enum):
    accepted = "accepted"
    running = "running"
    successful = "successful"
    failed = "failed"
    dismissed = "dismissed"


class JobControlOptions(Enum):
    sync_execute = "sync-execute"
    async_execute = "async-execute"
    dismiss = "dismiss"


class JobInfo(BaseModel):
    model_config = ConfigDict(
        # allow for extensions, e.g., using field name prefix "x-"
        extra="allow",
    )

    jobID: str
    processID: str | None = None
    type: Literal["process"] = "process"
    status: JobStatus
    message: str | None = None
    created: AwareDatetime | None = None
    started: AwareDatetime | None = None
    finished: AwareDatetime | None = None
    updated: AwareDatetime | None = None
    # noinspection Pydantic
    progress: int | None = Field(None, ge=0, le=100)
    links: list[Link] | None = None
    # -- recognized extensions
    traceback: str | list[str] | None = Field(None, alias="x-traceback")


class JobList(BaseModel):
    jobs: list[JobInfo]
    links: list[Link]


class QualifiedValue(Format):
    value: InlineValue


JobResult: TypeAlias = Link | QualifiedValue | InlineValue


# noinspection PyTypeChecker
class JobResults(RootModel[dict[str, JobResult] | None]):
    root: dict[str, JobResult] | None = None


# ---------------------------------------------------------------------
#    Other
# ---------------------------------------------------------------------


class ApiError(BaseModel):
    """
    API error based on RFC 7807
    """

    model_config = ConfigDict(
        # allow for extensions, e.g., using field name prefix "x-"
        extra="allow",
    )

    type: str
    title: str | None = None
    status: int | None = None
    detail: str | None = None
    instance: str | None = None
    # -- recognized extensions
    traceback: str | list[str] | None = Field(None, alias="x-traceback")


Format.model_rebuild()
Discriminator.model_rebuild()
ProcessDescription.model_rebuild()
ProcessRequest.model_rebuild()
QualifiedValue.model_rebuild()
