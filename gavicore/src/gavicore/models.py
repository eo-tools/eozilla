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
    """The optional data type of [Schema][gavicore.models.Schema]."""

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
        json_schema_extra={"additionalProperties": True},
    )

    # general
    type: DataType | None = None
    """Schema type."""
    title: str | None = None
    """Schema type."""
    description: str | None = None
    """Schema type."""
    enum: list | None = Field(None, min_length=1)
    """Schema type."""
    default: Any | None = None
    """Optional default value."""
    nullable: bool | None = False
    """Whether the value can have value `null` (Python `None`)."""
    readOnly: bool | None = False
    """Whether the value is read-only. Not used."""
    writeOnly: bool | None = False
    """Whether the value is write-only. Not used."""
    example: Any | None = None
    """Example value. Deprecated, use `examples`."""
    examples: list[Any] | None = None
    """One or more example values."""
    deprecated: bool | None = False
    """Whether the value is deprecated.."""
    # type "number" and "integer"
    minimum: int | float | None = None
    """Minimum value for numeric values."""
    maximum: int | float | None = None
    """Maximum value for numeric values."""
    exclusiveMinimum: bool | None = False
    """Whether the minimum value is exclusive."""
    exclusiveMaximum: bool | None = False
    """Whether the maximum value is exclusive."""
    multipleOf: float | None = Field(None, gt=0.0)
    """A numeric value must be divisible by this factor without rest."""
    # type "string"
    minLength: int | None = Field(0, ge=0)
    """Minimum length of a string value."""
    maxLength: int | None = Field(None, ge=0)
    """Maximum length of a string value."""
    format: str | None = None
    """Format of a string value."""
    pattern: str | None = None
    """Pattern of a string value."""
    contentMediaType: str | None = None
    """Content media type of a binary/string value."""
    contentEncoding: str | None = None
    """Content encoding a binary/string value."""
    contentSchema: str | None = None
    """Content schema of a binary/string value."""
    # type "array"
    items: Schema | None = None
    """Schema of the items of an array value."""
    minItems: int | None = Field(0, ge=0)
    """Minimum number of items of an array value."""
    maxItems: int | None = Field(None, ge=0)
    """Maximum number of items of an array value."""
    uniqueItems: bool | None = False
    """?"""
    # type "object"
    properties: dict[str, Schema] | None = None
    """Schemas of the properties of an object value."""
    required: list[str] | None = Field(None, min_length=1)
    """List of names of required properties of an object value."""
    minProperties: int | None = Field(0, ge=0)
    """Minimum number of properties of an object value."""
    maxProperties: int | None = Field(None, ge=0)
    """Maximum number of properties of an object value."""
    additionalProperties: Schema | bool | None = True
    """The common schema for additional properties of an object value.
    If a boolean is provided, whether or not additional properties 
    are allowed."""
    # operators
    not_: Schema | None = Field(None, alias="not")
    """A value must not match the `not`-schema. Alias is `not`."""
    allOf: list[Schema] | None = None
    """A value must match all of the schemas in the `allOf` list."""
    oneOf: list[Schema] | None = None
    """A value must match one of the schemas in the `oneOf` list."""
    anyOf: list[Schema] | None = None
    """A value must match any of the schemas in the `anyOf` list."""
    discriminator: Discriminator | None = None
    """Optional discriminator."""
    # refs
    id: str | None = Field(None, alias="$id", min_length=1)
    """Schema identifier. Alias is `$id`."""
    ref: str | None = Field(None, alias="$ref", min_length=1)
    """Schema reference. Alias is `$ref`."""

    def to_json_dict(self) -> dict[str, Any]:
        """Convert this model into a JSON-serializable `dict`."""
        return self.model_dump(
            mode="json", exclude_defaults=True, exclude_unset=True, by_alias=True
        )


class Discriminator(BaseModel):
    """
    OpenAPI discriminator used in conjunctions with
    [`oneOf`][gavicore.models.Schema.oneOf]/[`anyOf`][gavicore.models.Schema.anyOf]
    given that

    - all entries are references of the form `{"$ref": "#/..."`}` and
    - the referred schemas have type "object" and
    - the referred schemas have a common property
      whose value can be used to discriminate their meta-type.
    """

    propertyName: str = Field(..., min_length=1)
    """The common property's name. Required."""

    mapping: dict[str, str] | None = None
    """Optional mapping of possible values of the common property
    to schemas references."""


# ---------------------------------------------------------------------
#    Common
# ---------------------------------------------------------------------


class Link(BaseModel):
    """A link."""

    href: str
    """The link's URL. Required."""

    rel: str | None = Field(None, examples=["service"])
    """The link's relation."""

    type: str | None = Field(None, examples=["application/json"])
    """The link's mime-type."""

    hreflang: str | None = Field(None, examples=["en"])
    """The natural language used by the URL."""

    title: str | None = None
    """The link's title."""


# ---------------------------------------------------------------------
#    Service
# ---------------------------------------------------------------------


class Capabilities(BaseModel):
    title: str | None = Field(None, examples=["Example processing server"])
    """Capability title."""

    description: str | None = Field(
        None,
        examples=["Example server implementing the OGC API - Processes 1.0 Standard"],
    )
    """Capability description."""

    links: list[Link]
    """Related links."""


class ConformanceDeclaration(BaseModel):
    """Declaration that describes the supported conformance classes."""

    conformsTo: list[str]
    """The list of conformance classes."""


class CRS(Enum):
    """Predefined CRS IDs."""

    CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    """CRS-84."""
    CRS84H = "http://www.opengis.net/def/crs/OGC/0/CRS84h"
    """CRS-84h."""


class Bbox(BaseModel):
    """A geographical bounding box."""

    bbox: list[float] = Field(..., max_length=4, min_length=4)
    """The coordinates of the bounding box given as (x1, y1, x2, y2)."""

    crs: CRS | None = CRS.CRS84
    """The coordinate reference system of the coordinates."""


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
"""An inline value."""


class Metadata(BaseModel):
    """A related metadata reference."""

    title: str | None = None
    """Metadata's title."""

    role: str | None = None
    """Metadata's role."""

    href: str | None = None
    """Metadata's URL."""


class AdditionalParameter(BaseModel):
    """Additional parameter. Legacy, do not use."""

    name: str
    """Parameter name."""
    value: list[str | float | int | list[dict[str, Any]] | dict[str, Any]]
    """Parameter values."""


class AdditionalParameters(Metadata):
    """Additional parameters. Legacy, do not use."""

    parameters: list[AdditionalParameter] | None = None
    """The list of parameters."""


class DescriptionType(BaseModel):
    """Base class for description/metadata types."""

    model_config = ConfigDict(
        # allow for extensions usually prefixed by "x-", e.g., "x-ui"
        extra="allow",
        json_schema_extra={"additionalProperties": True},
    )

    title: str | None = None
    """Human-readable title."""

    description: str | None = None
    """Description text. May contain rich-text markups (markdown)."""

    keywords: list[str] | None = None
    """Optional list of keywords."""

    metadata: list[Metadata] | None = None
    """Optional list of related metadata."""

    additionalParameters: AdditionalParameters | None = None
    """Optional list of additional parameters. Mostly ignored."""


class Format(BaseModel):
    """Specified a value's data type and encoding."""

    mediaType: str | None = None
    """The value's media / mime type."""

    encoding: str | None = None
    """The value's text encoding. For text values only."""

    schema_: AnyUrl | Schema | None = Field(None, alias="schema")
    """The OpenAPI schema."""


# ---------------------------------------------------------------------
#    Process
# ---------------------------------------------------------------------


class InputDescription(DescriptionType):
    """Description of an input of a process."""

    minOccurs: int | None = 1
    """Minimum number of occurrences of this input. 
    Usually ignored as an array schema is more flexible."""

    maxOccurs: int | Literal["unbounded"] | None = None
    """Maximum number of occurrences of this input. 
    Usually ignored as an array schema is more flexible."""

    schema_: Schema = Field(..., alias="schema")
    """The OpenAPI schema of the input value(s)."""


class OutputDescription(DescriptionType):
    """Description of an output of a process."""

    schema_: Schema = Field(..., alias="schema")
    """The OpenAPI schema of the output value."""


class TransmissionMode(Enum):
    """How a process execution will deliver its results."""

    value = "value"
    """By inline value."""

    reference = "reference"
    """By reference such as a link."""


class ProcessSummary(DescriptionType):
    """A brief process descriptions lacking details of inputs and outputs."""

    id: str
    """Process identifier."""

    version: str
    """Process version number."""

    jobControlOptions: list[JobControlOptions] | None = None
    """Available options to control process execution."""

    outputTransmission: list[TransmissionMode] | None = None
    """Available output transmission modes."""

    links: list[Link] | None = None
    """Related links."""


class ProcessList(BaseModel):
    """A list of process summaries."""

    processes: list[ProcessSummary]
    """The process summaries"""

    links: list[Link]
    """Related links."""


class ProcessDescription(ProcessSummary):
    """Description of a process."""

    inputs: dict[str, InputDescription] | None = None
    """Descriptions of the process inputs."""

    outputs: dict[str, OutputDescription] | None = None
    """Descriptions of the process outputs."""


class Output(BaseModel):
    """Expected output of a process execution."""

    format: Format | None = None
    """Desired format."""

    transmissionMode: TransmissionMode | None = TransmissionMode.value
    """Desired transmission mode."""


class ResponseType(Enum):
    """Expected process execution result type."""

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
    """Optional callback URI to notify about a successfully executed job.."""

    inProgressUri: AnyUrl | None = None
    """Optional callback URI to notify about the incremental progress made by a job."""

    failedUri: AnyUrl | None = None
    """Optional callback URI to notify in case of a job failure."""


class ProcessRequest(BaseModel):
    """A request for a process execution."""

    inputs: dict[str, Any] | None = None
    """Optional process inputs given as key-value mapping.
    Values may be of any JSON-serializable type accepted by
    the given process."""

    outputs: dict[str, Output] | None = None
    """Optional process outputs given as key-value mapping.
    Values are of type [Output][gavicore.models.Output]
    supported by the given process."""

    subscriber: Subscriber | None = None
    """Optional subscriber of type
    [Subscriber][gavicore.models.Subscriber] comprising callback
    URLs that are informed about process status changes
    while the processing takes place."""

    response: ResponseType | None = ResponseType.raw
    """Optional response type given as key-value mapping. 
    Maybe just ignored."""


# ---------------------------------------------------------------------
#    Job
# ---------------------------------------------------------------------


class JobStatus(Enum):
    """Status of a job."""

    accepted = "accepted"
    running = "running"
    successful = "successful"
    failed = "failed"
    dismissed = "dismissed"


class JobControlOptions(Enum):
    """Options to control job execution."""

    sync_execute = "sync-execute"
    async_execute = "async-execute"
    dismiss = "dismiss"


class JobInfo(BaseModel):
    """Information about a job."""

    model_config = ConfigDict(
        # allow for extensions, e.g., using field name prefix "x-"
        extra="allow",
    )

    jobID: str
    """The job identifier."""

    processID: str | None = None
    """The job's process identifier."""

    type: Literal["process"] = "process"
    """The job type (always "process", ignored)."""

    status: JobStatus
    """The job status."""

    message: str | None = None
    """The success, progress, or failure message."""

    created: AwareDatetime | None = None
    """Job creation time."""

    started: AwareDatetime | None = None
    """Job start time."""

    finished: AwareDatetime | None = None
    """Job end time."""

    updated: AwareDatetime | None = None
    """Job update time."""

    # noinspection Pydantic
    progress: int | None = Field(None, ge=0, le=100)
    """The progress in percent in the range 0 to 100."""

    links: list[Link] | None = None
    """Related links."""

    # -- recognized extensions
    traceback: str | list[str] | None = Field(None, alias="x-traceback")
    """Server-side traceback in case of failure."""


class JobList(BaseModel):
    """A list of jobs."""

    jobs: list[JobInfo]
    """The job information list."""

    links: list[Link]
    """Related links."""


class QualifiedValue(Format):
    """A qualified value."""

    value: InlineValue
    """The (JSON) value."""


JobResult: TypeAlias = Link | QualifiedValue | InlineValue
"""The type representing the a single result of a job."""


# noinspection PyTypeChecker
class JobResults(RootModel[dict[str, JobResult] | None]):
    """
    A job's results.
    Basically a mapping from output name to [JobResult][gavicore.models.JobResult].
    """

    root: dict[str, JobResult] | None = None


# ---------------------------------------------------------------------
#    Other
# ---------------------------------------------------------------------


class ApiError(BaseModel):
    """
    API error information based on RFC 7807.
    """

    model_config = ConfigDict(
        # allow for extensions, e.g., using field name prefix "x-"
        extra="allow",
    )

    type: str
    """Error type."""

    title: str | None = None
    """Error title."""

    status: int | None = None
    """HTTP status code."""

    detail: str | None = None
    """Detailed error message."""

    instance: str | None = None
    """Instance information."""

    # -- recognized extensions
    traceback: str | list[str] | None = Field(None, alias="x-traceback")
    """Server-side traceback."""


Format.model_rebuild()
Discriminator.model_rebuild()
ProcessDescription.model_rebuild()
ProcessRequest.model_rebuild()
QualifiedValue.model_rebuild()
