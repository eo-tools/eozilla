from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

CwlVersion: TypeAlias = Literal["v1.0"]
CommandLineToolClass: TypeAlias = Literal["CommandLineTool"]


class CwlBaseModel(BaseModel):
    """Base model for the supported CWL subset."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DockerRequirement(CwlBaseModel):
    """Subset of CWL DockerRequirement."""

    docker_pull: str = Field(alias="dockerPull")


class Requirements(CwlBaseModel):
    """Supported CWL requirements."""

    docker_requirement: DockerRequirement = Field(alias="DockerRequirement")


class InputBinding(CwlBaseModel):
    """Subset of CWL inputBinding."""

    prefix: str | None = None
    separate: bool | None = None


class OutputBinding(CwlBaseModel):
    """Subset of CWL outputBinding."""

    glob: str


class EnumType(CwlBaseModel):
    """Inline CWL enum type."""

    type: Literal["enum"]
    symbols: list[str]


class ArrayType(CwlBaseModel):
    """Inline CWL array type."""

    type: Literal["array"]
    items: SupportedType


PrimitiveTypeName: TypeAlias = Literal[
    "string", "int", "long", "float", "double", "boolean"
]
FileSystemTypeName: TypeAlias = Literal["File", "Directory"]
ScalarTypeName: TypeAlias = PrimitiveTypeName | FileSystemTypeName

SupportedType: TypeAlias = ScalarTypeName | EnumType | ArrayType


class CwlType(RootModel[SupportedType]):
    """Root wrapper for a supported CWL type expression."""

    @model_validator(mode="before")
    @classmethod
    def normalize_optional_type(cls, value: Any) -> Any:
        if isinstance(value, str) and value.endswith("?"):
            return value[:-1]
        return value

    @property
    def is_file(self) -> bool:
        return self.root == "File"

    @property
    def is_directory(self) -> bool:
        return self.root == "Directory"

    @property
    def is_array(self) -> bool:
        return isinstance(self.root, ArrayType)

    @property
    def is_enum(self) -> bool:
        return isinstance(self.root, EnumType)


class InputParameter(CwlBaseModel):
    """Supported subset of a CWL input parameter."""

    type: CwlType
    label: str | None = None
    doc: str | None = None
    default: Any | None = None
    input_binding: InputBinding | None = Field(default=None, alias="inputBinding")

    @property
    def required(self) -> bool:
        return self.default is None


class OutputParameter(CwlBaseModel):
    """Supported subset of a CWL output parameter."""

    type: CwlType
    label: str | None = None
    doc: str | None = None
    output_binding: OutputBinding = Field(alias="outputBinding")


class Inputs(RootModel[dict[str, InputParameter]]):
    pass


class Outputs(RootModel[dict[str, OutputParameter]]):
    pass


class CommandLineTool(CwlBaseModel):
    """Entry-point class for the supported CWL CommandLineTool subset."""

    cwl_version: CwlVersion = Field(alias="cwlVersion")
    class_: CommandLineToolClass = Field(alias="class")
    label: str | None = None
    doc: str | None = None
    base_command: str | list[str] = Field(alias="baseCommand")
    requirements: Requirements
    inputs: Inputs
    outputs: Outputs

    @model_validator(mode="after")
    def reject_unsupported_runtime_features(self) -> "CommandLineTool":
        # The ConfigDict(extra="forbid") already rejects unknown fields such as
        # valueFrom, outputEval, scatter, steps, hints, arguments, etc.
        # This method exists as the explicit policy hook for future checks.
        return self


CwlDocument = CommandLineTool
