from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

"""Pydantic models for a deliberately small CWL subset.

This module models the part of CWL that is useful for deploying simple
containerized processes through OGC API - Processes Part 2: Deploy, Replace,
Update.

The goal is not to implement CWL as a general workflow language or to provide a
complete CWL runner. Instead, CWL is treated as a deployment description format:
it describes a command-line tool, its container image, its inputs, its outputs,
and the basic command-line bindings needed to execute it.

Supported concepts include:

* `CommandLineTool`
* `cwlVersion: v1.0`
* `baseCommand`
* `DockerRequirement`
* primitive input types
* `File` and `Directory`
* optional types such as `string?`
* arrays
* enums
* defaults
* `label` and `doc`
* basic `inputBinding`
* basic `outputBinding.glob`

This subset is intentionally restrictive. It excludes features that would require
a substantially more complex CWL execution engine, such as workflows, scatter,
sub-workflows, JavaScript expressions, `valueFrom`, `outputEval`, dynamic runtime
expressions, and step-level input expressions.

For an OGC API - Processes Part 2 server, this is usually the more useful
boundary: the server can import a CWL document into its own internal process
model, publish the corresponding process description, and execute the referenced
container with validated inputs. More advanced CWL features can be added later,
but they should be treated as explicit extensions rather than assumed support for
the full CWL specification.
"""


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
