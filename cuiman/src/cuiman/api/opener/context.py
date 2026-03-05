#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from gavicore.models import (
    InlineOrRefValue,
    InlineValue,
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
)

if TYPE_CHECKING:
    from cuiman.api.config import ClientConfig


@dataclass
class JobResultOpenContext:
    """The context around the results of a process job that allows opening
    the job results or a particular job result.
    Includes `job_results` of type [JobResults][JobResults] and the
    context surrounding it.
    The context object is passed to the methods of [JobResultOpener][JobResultOpener].
    """

    config: "ClientConfig"
    """Configuration of the client."""

    process_description: ProcessDescription | None
    """Description of the process that produced the results."""

    job_id: str
    """ID of the job."""

    job_results: JobResults
    """Results of a job."""

    output_name: str | None
    """
    Name of the output that should be opened.
    If given, an opener must accept that name and be able to
    return a value of that name from the 
    [open_result][JobResultOpener.open_result] method.
    """

    data_type: type | None
    """
    Data type of the output that should be opened.
    If given, an opener must accept that value and be able to
    return a value of that type from the 
    [open_result][JobResultOpener.open_result] method.
    """

    options: dict[str, Any]
    """Opener-specific options."""

    @property
    def output_description(self) -> OutputDescription | None:
        process_description = self.process_description
        if process_description and isinstance(process_description.outputs, dict):
            outputs = process_description.outputs
            output_name = _ensure_output_name(self.output_name, outputs)
            return outputs.get(output_name)
        return None

    @property
    def output_value(self) -> Link | QualifiedValue | InlineValue | None:
        """Output value.

        If `output_name` is given, the value of that output.
        If `output_name` is not given, the job results must
        comprise only a single output or contain an output value
        named `"return_value"`.
        Otherwise, the output value is `None`.
        """
        results = self.job_results.root
        if isinstance(results, dict):
            output_name = _ensure_output_name(self.output_name, results)
            inline_or_ref_value = results.get(output_name)
            if isinstance(inline_or_ref_value, InlineOrRefValue):
                return inline_or_ref_value.root
        return None

    @property
    def output_link(self) -> Link | None:
        """Output link.
        May be `None` if [`output_value`][output_value] is not a link.
        """
        return _to_link(self.output_value)

    @property
    def output_qualified_value(self) -> QualifiedValue | None:
        """Qualified output value.
        May be `None` if [`output_value`][output_value] is not a qualified value.
        """
        return _to_qualified_value(self.output_value)

    @property
    def output_media_type(self) -> str | None:
        """The output value's media type.
        If provided, the media type value is usually data format's MIME-type string.
        May be `None` if [`output_value`][output_value] does not have
        a media type assigned.
        """
        value = self.output_value
        if isinstance(value, Link) and value.type:
            return value.type
        if isinstance(value, QualifiedValue) and value.mediaType:
            return value.mediaType
        return None


def _to_link(value: Any) -> Link | None:
    return _to_model_instance(value, Link, ("href",))


def _to_qualified_value(value: Any) -> QualifiedValue | None:
    return _to_model_instance(value, QualifiedValue, ("value",))


T = TypeVar("T", bound=BaseModel)


def _to_model_instance(
    value: Any, model_cls: type[T], required: tuple[str, ...]
) -> T | None:
    if isinstance(value, model_cls):
        return value
    # Since value is not of type `model_cls`, we try to create an
    # instance from the value's raw (JSON) value.
    # For a reason that is still unclear,
    # pydantic does not always deserialize JSON value from job results
    # into model instances.
    raw_value: Any = None
    if isinstance(value, QualifiedValue):
        raw_value = value.value.model_dump()
    elif isinstance(value, InlineValue):
        raw_value = value.root
    if isinstance(raw_value, dict) and all(r in raw_value for r in required):
        try:
            return model_cls(**raw_value)
        except ValueError:
            pass
    return None


def _ensure_output_name(output_name: str | None, mapping: dict[str, Any]) -> str:
    if output_name:
        return output_name
    if mapping and len(mapping) == 1:
        return next(iter(mapping))
    return "return_value"
