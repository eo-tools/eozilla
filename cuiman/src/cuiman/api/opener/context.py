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
        if self.output_name:
            return self.process_description.outputs.get(
                self.output_name or "return_value"
            )
        return None

    @property
    def output_value(self) -> Link | QualifiedValue | InlineValue | None:
        """Output value.
        The value of either a given `output_name`
        or the output name `"return_value"`.
        """
        results = self.job_results.root
        return (
            results.get(self.output_name or "return_value")
            if isinstance(results, dict)
            else None
        )

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
        return self.options.get("media_type")


def _to_link(value: Any) -> Link | None:
    return value if isinstance(value, Link) else None


def _to_qualified_value(value: Any) -> QualifiedValue | None:
    return value if isinstance(value, QualifiedValue) else None
