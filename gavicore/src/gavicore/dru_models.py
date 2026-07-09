#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, Field

from .models import Link, OgcBaseModel, ProcessDescription

# ---------------------------------------------------------------------
#    OGC Application Package and Workflow descriptions
# ---------------------------------------------------------------------


class OGCApplicationPackage(BaseModel):
    """
    An OGC Application Package is a document that describes a process in
    sufficient detail so that an implementation of this Standard can
    dynamically deploy that process and make it accessible via an the
    processes API defined in "OGC API - Processes - Part 1: Core".

    For more information, see: /req/ogcapppkg/schema
    """

    process_description: OGCApplicationPackageProcessDescription | None = Field(
        None, alias="processDescription"
    )
    """Process description of a given process."""

    execution_uni: ExecutionUnitBase | list[ExecutionUnitBase] = Field(
        alias="executionUnit"
    )
    """The execution unit of process."""


class OGCApplicationPackageProcessDescription(BaseModel):
    """Wrapper around `ProcessDescription` to insert additional field name."""

    process: ProcessDescription | None = None
    """The process description."""


class CWLDescription(BaseModel):
    """
    Possible encoding of an execution unit as CWL.
    """

    media_type: Annotated[Literal["application/cwl"], Field(..., alias="mediaType")]
    """Media type used to identify the execution unit type.
    Must always be 'application/cwl'."""

    value: str | None = None
    """JSON-encoded CWL document."""


class ContainerImage(BaseModel):
    """The execute unit is a container image."""

    type: Literal["docker", "oci"]
    """Type of container image."""

    value: ExecutionUnitContainer | None = None
    """Description of container image"""


class ExecutionUnitContainer(OgcBaseModel):
    """Execution unit described by a container image."""

    image: str
    """Container image reference for the execution unit."""

    deployment: Literal["local", "remote", "hpc", "cloud"] | None = None
    """Deployment information for the execution unit."""

    config: ContainerConfig | None = None
    """Optional configuration for image execution."""

    bindings: ContainerBindings | None = None
    """Binding properties for inputs and outputs."""


class ContainerConfig(OgcBaseModel):
    """Hardware requirements and configuration properties
    for executing the process."""

    cpu_min: int | None = Field(None, ge=1, alias="cpuMin")
    """Minimum number of CPUs required to run the process (unit is CPU core)."""

    cpu_max: int | None = Field(None, alias="cpuMax")
    """Maximum number of CPU dedicated to the process (unit is CPU core)."""

    memory_min: int | float | None = Field(None, alias="memoryMin")
    """Minimum RAM memory required to run the application (unit is GB)."""

    memory_max: int | float | None = Field(None, alias="memoryMax")
    """Maximum RAM memory dedicated to the application (unit is GB)."""

    storage_temp_min: int | float | None = Field(None, alias="storageTempMin")
    """ Minimum required temporary storage size (unit is GB)."""

    storage_outputs_min: int | float | None = Field(None, alias="storageOutputsMin")
    """Minimum required output storage size (unit is GB)."""

    job_timeout: int | float | None = Field(None, alias="jobTimeout")
    """Timeout delay for a job execution (in seconds)."""


class ContainerBindings(BaseModel):
    """Input and output bindings of a container image execution unit."""

    input_bindings: InputBinding | None = Field(None, alias="inputBindings")
    """Input bindings."""

    output_bindings: OutputBinding | None = Field(None, alias="outputBindings")
    """Output bindings."""


class InputBinding(BaseModel):
    """Defines how to specify the input for the execution unit.

    - The value of various properties defined below can be expressions.
      - The expression language SHALL be JavaScript(???).
    - The "$(...)" syntax can be used to reference the current input or other
        process inputs in an expression.
        - The value "self" refers to the value of the current input.
        - The value "inputs.<other_input>" refers to the value of another
        process input.
        - If the input is defined as a string of format "file" or "directory"
        then the meta-values ".path", ".basename", ".nameroot" and ".nameext"
        can be used to manipulate file or directory name without having to
        resort to complex regular expressions.
            - ".path" returns the path of a file name without the file name
            - ".basename" returns the name of the file without the path
            - ".nameroot" returns the basename without any extension
            - ".nameext" returns the extension of the basename
    """

    prefix: str | None = None
    """Command line prefix to add before the value."""

    position: int | str | None = None
    """
    - The zero-based sorting key.
    - The value can be an integer or a string.
    - If the value is a string then it should be an expression that evaluates
    to a single integer value or null.
    """

    value_from: str | None = Field(None, alias="valueFrom")
    """
    - If valueFrom is a constant string value, use this as the value.
    - If valueFrom is an expression, evaluate the expression to yield the
    actual value to use to build the command line.
    - If the value of the associated input parameter is null, valueFrom is
    not evaluated and nothing is added to the command line.
    """

    item_separator: str | None = Field(None, alias="itemSeparator")
    """ Join the array elements into a single string with the elements
    separated by itemSeparator."""

    shell_quote: bool | None = Field(None, alias="shellQuote")
    """
    - A Boolean that controls whether the value is quoted on the command.
    - A value of true (or if shecllQuote is not provided) means that the
      implementation SHALL not permit the interpretation of any shell
      metacharacters or directives.
    - A value of false should be used to inject metacharacters for operations
    such as pipes.
    """


class OutputBinding(OgcBaseModel):
    """Defines how to retrieve the output result from the command."""

    glob: str | list[str] | None = None
    """
    - Wildcard pattern to find the output on disk or mounted volume.
    - Uses UNIX "glob" wildcard patterns (see: "man 7 glob").
    - See inputBinding.yaml (modeled as InputBinding) for referencing
      input values in an output
      binding "glob" expression.
    """


class GenericExecutionUnit(BaseModel):
    """A generic execution unit.

    The standard notes:
        The execution unit is not Docker/OCI or CWL and cannot be properly
        described via the "mediaType" property of a qualified value
        using an RFC 2046 media type (e.g. an "R" or "Python" script).
        In this case a community-defined or custom token may be used
        with the "type" property.
    """

    type: str
    """Type of execution unit"""


ExecutionUnitBase: TypeAlias = (
    Link | CWLDescription | ContainerImage | GenericExecutionUnit
)
"""Execution unit encoding of a process."""

ContainerBindings.model_rebuild()
ExecutionUnitContainer.model_rebuild()
ContainerImage.model_rebuild()
OGCApplicationPackage.model_rebuild()
