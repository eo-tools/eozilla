#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


from gavicore.models import (
    JobResults,
    ProcessDescription,
    OutputDescription,
    Link,
    QualifiedValue,
    InlineOrRefValue,
    InlineValue,
)

if TYPE_CHECKING:
    from cuiman.api.config import ClientConfig


@dataclass
class OpenerContext:
    """Context object passed to the methods of [Opener][Opener]."""

    config: "ClientConfig"
    """Configuration of the client."""

    process_description: ProcessDescription
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
    [open_result][Opener.open_result] method.
    """

    data_type: type | None
    """
    Data type of the output that should be opened.
    If given, an opener must accept that value and be able to
    return a value of that type from the 
    [open_result][Opener.open_result] method.
    """

    options: dict[str, Any]
    """Opener-specific options."""

    @property
    def output_description(self) -> OutputDescription | None:
        outputs = self.process_description.outputs
        if outputs:
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
    if isinstance(value, Link):
        return value
    _value: dict | None = None
    if isinstance(value, QualifiedValue):
        _value = value.value.model_dump()
    elif isinstance(value, InlineValue):
        _value = value.root
    if isinstance(_value, dict) and "href" in _value:
        try:
            return Link(**_value)
        except ValueError:
            pass
    return None


def _to_qualified_value(value: Any) -> QualifiedValue | None:
    if isinstance(value, QualifiedValue):
        return value
    _value: dict | None = None
    if isinstance(value, InlineValue):
        _value = value.root
    if isinstance(_value, dict) and "value" in _value:
        try:
            return QualifiedValue(**_value)
        except ValueError:
            pass
    return None


def _ensure_output_name(output_name: str | None, mapping: dict[str, Any]) -> str:
    if output_name:
        return output_name
    if mapping and len(mapping) == 1:
        return next(iter(mapping))
    return "return_value"
