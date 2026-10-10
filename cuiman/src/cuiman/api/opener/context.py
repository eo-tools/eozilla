#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from gavicore.models import (
    JobResults,
    Link,
    OutputDescription,
    ProcessDescription,
    QualifiedValue,
)

from .errors import JobResultOpenError

if TYPE_CHECKING:
    from cuiman.api.config import ClientConfig

_UNSELECTED = object()


@dataclass
class JobResultOpenContext:
    """One selected target and optional facts about its producing job.

    Supply ``job_results`` to select an original output during construction,
    or supply ``value`` directly without requiring a job. Job output values are
    copied so opening cannot mutate the original results. Every opener receives
    the same selected target rather than selecting a sibling from source facts.

    Raises:
        JobResultOpenError: If no target is supplied, results are empty, an output
            is missing, or multiple outputs require explicit selection.
    """

    config: "ClientConfig"
    """Configuration of the client."""

    job_id: str | None = None
    """Optional ID of the producing job."""

    job_results: JobResults | None = None
    """Original results, retained as source facts rather than reader targets."""

    process_description: ProcessDescription | None = None
    """Description of the process that produced the results."""

    output_name: str | None = None
    """
    Name of the selected original output, if known. A sole job output's name is
    resolved during construction. Multiple outputs require an explicit name;
    an output named ``return_value`` has no special precedence.
    """

    data_type: type | None = None
    """
    Data type of the output that should be opened.
    If given, an opener must accept that value and be able to
    return a value of that type from the 
    [open_job_result()][cuiman.api.opener.JobResultOpener.open_job_result] method.
    """

    _media_type: str | None = None
    """Explicit media type for the selected target.
    Supplied by the caller or normalized from target metadata at the client
    entry point. If given, provides or overrides the output's media type.
    Use [output_media_type][cuiman.api.opener.JobResultOpenContext.output_media_type] to make use of
    the effective media type.  
    """

    options: dict[str, Any] = field(default_factory=dict, repr=False)
    """Opener-specific options."""

    resolved_options: dict[str, Any] = field(default_factory=dict, repr=False)
    """Non-secret effective reader options from the latest opening attempt."""

    option_sources: dict[str, str] = field(default_factory=dict, repr=False)
    """Source labels for effective options, keyed by dotted option paths."""

    value: Any = field(default=_UNSELECTED, repr=False)
    """Authoritative selected value. Explicit None is a valid target."""

    location: str | None = None
    """Effective selected location, if known; may override the value's location.

    Derived from Link, qualified, and supported path-like values when omitted.
    This field does not imply that relative locations have been resolved.
    """

    document_href: str | None = None
    """Effective containing result-document URI supplied by the transport.

    Used only as source context for inline metadata; never guessed from api_url.
    """

    def __post_init__(self) -> None:
        """Select and copy a job output, then normalize its location without I/O."""
        if self.value is _UNSELECTED:
            if self.job_results is None:
                raise JobResultOpenError("No selected value or job results provided")
            results = self.job_results.root or {}
            self.output_name = _select_output_name(self.output_name, results)
            self.value = deepcopy(results[self.output_name])
        if self.location is None:
            self.location = _get_location(self.value)

    @property
    def output_description(self) -> OutputDescription | None:
        """Schema and description for the selected original output, if known.

        The process schema never selects an output independently of job results.
        """
        process_description = self.process_description
        if (
            process_description
            and isinstance(process_description.outputs, dict)
            and self.output_name is not None
        ):
            return process_description.outputs.get(self.output_name)
        return None

    @property
    def output_value(self) -> Any:
        """The authoritative selected value, also available as ``value``."""
        return self.value

    @property
    def output_link(self) -> Link | None:
        """Output link.
        May be `None` if `output_value` is not a link.
        """
        return _to_link(self.output_value)

    @property
    def output_qualified_value(self) -> QualifiedValue | None:
        """Qualified output value.
        May be `None` if `output_value` is not a qualified value.
        """
        return _to_qualified_value(self.output_value)

    @property
    def output_media_type(self) -> str | None:
        """The output value's media type.
        If provided, the media type value is usually data format's MIME-type string.
        May be `None` if `output_value` does not have
        a media type assigned.
        """
        if self._media_type is not None:
            return self._media_type
        qualified_value = self.output_qualified_value
        if qualified_value is not None:
            return qualified_value.mediaType
        link = self.output_link
        if link is not None:
            return link.type
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
        raw_value = value.model_dump().get("value")
    else:
        raw_value = value
    if isinstance(raw_value, dict) and all(r in raw_value for r in required):
        try:
            return model_cls(**raw_value)
        except ValueError:
            pass
    return None


def _select_output_name(output_name: str | None, mapping: dict[str, Any]) -> str:
    if output_name is not None:
        if output_name not in mapping:
            raise JobResultOpenError(f"Job output {output_name!r} does not exist")
        return output_name
    if len(mapping) == 1:
        return next(iter(mapping))
    if not mapping:
        raise JobResultOpenError("Job results contain no outputs")
    raise JobResultOpenError("Multiple job outputs available; specify output_name")


def _get_location(value: Any) -> str | None:
    link = _to_link(value)
    if link is not None:
        return link.href
    qualified_value = _to_qualified_value(value)
    if qualified_value is not None:
        value = qualified_value.value
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, (str, Path)):
        return str(value)
    if isinstance(value, dict):
        for key in ("href", "url", "path"):
            location = value.get(key)
            if isinstance(location, (str, Path)):
                return str(location)
    return None


def _copy_options(value: Any) -> Any:
    """Copy option containers while retaining opaque runtime sessions/callables."""
    if isinstance(value, dict):
        return {key: _copy_options(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_options(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_options(item) for item in value)
    return value
