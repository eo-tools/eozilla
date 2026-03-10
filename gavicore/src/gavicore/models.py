#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Any, Optional, TypeAlias, Union

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field, RootModel

# ---------------------------------------------------------------------
#    JSONSchema
# ---------------------------------------------------------------------


class DataType(Enum):
    boolean = "boolean"
    integer = "integer"
    number = "number"
    string = "string"
    array = "array"
    object = "object"


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    # general
    type: Optional[DataType] = None
    title: Optional[str] = None
    description: Optional[str] = None
    enum: Optional[list] = Field(None, min_length=1)
    default: Optional[Any] = None
    nullable: Optional[bool] = False
    readOnly: Optional[bool] = False
    writeOnly: Optional[bool] = False
    example: Optional[Any] = None
    examples: Optional[Any] = None
    deprecated: Optional[bool] = False
    field_ref: Optional[str] = Field(None, alias="$ref")
    # type "number" and "integer"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    exclusiveMinimum: Optional[bool] = False
    exclusiveMaximum: Optional[bool] = False
    multipleOf: Optional[float] = Field(None, gt=0.0)
    # type "string"
    minLength: Optional[int] = Field(0, ge=0)
    maxLength: Optional[int] = Field(None, ge=0)
    format: Optional[str] = None
    pattern: Optional[str] = None
    contentMediaType: Optional[str] = None
    contentEncoding: Optional[str] = None
    contentSchema: Optional[str] = None
    # type "array"
    items: Optional[Union[list[Schema], Schema]] = None
    minItems: Optional[int] = Field(0, ge=0)
    maxItems: Optional[int] = Field(None, ge=0)
    uniqueItems: Optional[bool] = False
    # type "object"
    properties: Optional[dict[str, Schema]] = None
    required: Optional[list[str]] = Field(None, min_length=1)
    minProperties: Optional[int] = Field(0, ge=0)
    maxProperties: Optional[int] = Field(None, ge=0)
    additionalProperties: Optional[Union[Schema, bool]] = True
    # operators
    not_: Optional[Schema] = Field(None, alias="not")
    allOf: Optional[list[Schema]] = None
    oneOf: Optional[list[Schema]] = None
    anyOf: Optional[list[Schema]] = None
    discriminator: Optional[Discriminator] = None


class Discriminator(BaseModel):
    propertyName: Optional[str] = Field(None, min_length=1)
    mapping: Optional[dict[str, Schema]] = None


# ---------------------------------------------------------------------
#    Common
# ---------------------------------------------------------------------


class Link(BaseModel):
    href: str
    rel: Optional[str] = Field(None, examples=["service"])
    type: Optional[str] = Field(None, examples=["application/json"])
    hreflang: Optional[str] = Field(None, examples=["en"])
    title: Optional[str] = None


# ---------------------------------------------------------------------
#    Service
# ---------------------------------------------------------------------


class Capabilities(BaseModel):
    title: Optional[str] = Field(None, examples=["Example processing server"])
    description: Optional[str] = Field(
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
    crs: Optional[CRS] = CRS.CRS84


InlineValue: TypeAlias = Union[
    Any,
    bool,
    bytes,
    AnyUrl,
    date,
    AwareDatetime,
    str,
    int,
    float,
    list,
    dict[str, Any],
    Bbox,
]


class Metadata(BaseModel):
    title: Optional[str] = None
    role: Optional[str] = None
    href: Optional[str] = None


class AdditionalParameter(BaseModel):
    name: str
    value: list[Union[str, float, int, list[dict[str, Any]], dict[str, Any]]]


class AdditionalParameters(Metadata):
    parameters: Optional[list[AdditionalParameter]] = None


class DescriptionType(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[list[str]] = None
    metadata: Optional[list[Metadata]] = None
    additionalParameters: Optional[AdditionalParameters] = None


class Format(BaseModel):
    mediaType: Optional[str] = None
    encoding: Optional[str] = None
    schema_: Optional[Union[AnyUrl, Schema]] = Field(None, alias="schema")


# ---------------------------------------------------------------------
#    Process
# ---------------------------------------------------------------------


class MaxOccurs(Enum):
    unbounded = "unbounded"


class InputDescription(DescriptionType):
    minOccurs: Optional[int] = 1
    maxOccurs: Optional[Union[int, MaxOccurs]] = None
    schema_: Schema = Field(..., alias="schema")


class OutputDescription(DescriptionType):
    schema_: Schema = Field(..., alias="schema")


class TransmissionMode(Enum):
    value = "value"
    reference = "reference"


class ProcessSummary(DescriptionType):
    id: str
    version: str
    jobControlOptions: Optional[list[JobControlOptions]] = None
    outputTransmission: Optional[list[TransmissionMode]] = None
    links: Optional[list[Link]] = None


class ProcessList(BaseModel):
    processes: list[ProcessSummary]
    links: list[Link]


class ProcessDescription(ProcessSummary):
    inputs: Optional[dict[str, InputDescription]] = None
    outputs: Optional[dict[str, OutputDescription]] = None


class Output(BaseModel):
    format: Optional[Format] = None
    transmissionMode: Optional[TransmissionMode] = TransmissionMode.value


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

    successUri: Optional[AnyUrl] = None
    inProgressUri: Optional[AnyUrl] = None
    failedUri: Optional[AnyUrl] = None


class ProcessRequest(BaseModel):
    inputs: Optional[dict[str, Any]] = None
    outputs: Optional[dict[str, Output]] = None
    response: Optional[ResponseType] = ResponseType.raw
    subscriber: Optional[Subscriber] = None


# ---------------------------------------------------------------------
#    Job
# ---------------------------------------------------------------------


class JobStatus(Enum):
    accepted = "accepted"
    running = "running"
    successful = "successful"
    failed = "failed"
    dismissed = "dismissed"


class JobType(Enum):
    process = "process"


class JobControlOptions(Enum):
    sync_execute = "sync-execute"
    async_execute = "async-execute"
    dismiss = "dismiss"


class JobInfo(BaseModel):
    model_config = ConfigDict(
        extra="allow",
    )

    processID: Optional[str] = None
    type: JobType
    jobID: str
    status: JobStatus
    message: Optional[str] = None
    created: Optional[AwareDatetime] = None
    started: Optional[AwareDatetime] = None
    finished: Optional[AwareDatetime] = None
    updated: Optional[AwareDatetime] = None
    # noinspection Pydantic
    progress: Annotated[int | None, Field(None, ge=0, le=100)] = None
    links: Optional[list[Link]] = None
    # --- Enhancements to the standard
    traceback: Optional[list[str]] = None


class JobList(BaseModel):
    jobs: list[JobInfo]
    links: list[Link]


class QualifiedValue(Format):
    value: InlineValue


InlineOrRefValue: TypeAlias = Link | QualifiedValue | InlineValue


# JobResults: TypeAlias = dict[str, InlineOrRefValue]
class JobResults(RootModel[Optional[dict[str, InlineOrRefValue]]]):
    root: Optional[dict[str, InlineOrRefValue]] = None


# ---------------------------------------------------------------------
#    Other
# ---------------------------------------------------------------------


class ApiError(BaseModel):
    """
    API error based on RFC 7807
    """

    model_config = ConfigDict(
        extra="allow",
    )

    type: str
    title: Optional[str] = None
    status: Optional[int] = None
    detail: Optional[str] = None
    instance: Optional[str] = None
    # --- Enhancements to the standard
    traceback: Optional[list[str]] = None


Format.model_rebuild()
Discriminator.model_rebuild()
ProcessDescription.model_rebuild()
ProcessRequest.model_rebuild()
QualifiedValue.model_rebuild()
