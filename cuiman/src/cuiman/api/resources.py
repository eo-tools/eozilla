#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Portable job result descriptions and local, metadata-only inspection."""

import base64
import json
from collections.abc import Iterator, Mapping
from html import escape
from types import MappingProxyType
from typing import Annotated, Any, Literal, TypeAlias, overload

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    PlainSerializer,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from gavicore.models import Link

DiscoveryState: TypeAlias = Literal["unresolved", "partial", "complete", "error"]
"""Completion of the requested semantic discovery view."""

CapabilityState: TypeAlias = Literal["available", "unavailable", "unknown"]
"""Candidate availability, independent of successful access to a payload."""


_JsonValue = Annotated[
    JsonValue,
    BeforeValidator(lambda value: _thaw_json(value)),
    AfterValidator(lambda value: _freeze_json(value)),
    PlainSerializer(lambda value: _thaw_json(value)),
]

_JsonObject = Annotated[
    Mapping[str, JsonValue],
    BeforeValidator(lambda value: _thaw_json(value)),
    AfterValidator(lambda value: _freeze_json(value)),
    PlainSerializer(lambda value: _thaw_json(value)),
]

_json_adapter: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)

_SNAPSHOT_CONFIG = ConfigDict(
    frozen=True,
    extra="forbid",
    validate_default=True,
    hide_input_in_errors=True,
    allow_inf_nan=False,
)


class ResourceDiagnostic(BaseModel):
    """A portable explanation of detection, validation, access, or traversal."""

    model_config = _SNAPSHOT_CONFIG

    code: str
    """Machine-readable diagnostic identifier supplied by the discovery adapter."""

    message: str
    """Human-readable explanation of the condition or failure."""

    severity: Literal["info", "warning", "error"] = "warning"
    """Severity of the reported condition."""

    details: _JsonObject = Field(default_factory=dict)
    """Read-only, non-secret JSON metadata providing additional context."""


class ResourceAction(BaseModel):
    """An opener or preview candidate identified within its execution runtime."""

    model_config = _SNAPSHOT_CONFIG

    id: str = Field(min_length=1)
    """Stable identifier of the opener or preview action within its runtime."""

    title: str = Field(min_length=1)
    """Display name of the candidate action."""

    runtime: str = Field(default="python", min_length=1)
    """Execution environment for the action, such as Python or a browser."""


class ResourceCapability(BaseModel):
    """An assessment snapshot, scoped to a runtime and non-secret settings.

    Available means that a candidate exists, without verifying payload access.
    An unknown assessment can describe pending or failed assessment through
    ``reason``. Scope may record the requested return type and configuration
    revision as portable metadata; it never contains runtime service objects.
    """

    model_config = _SNAPSHOT_CONFIG

    state: CapabilityState = "unknown"
    """Candidate availability; it does not indicate successful payload access."""

    candidates: tuple[ResourceAction, ...] = ()
    """Candidate opener or preview actions identified by the assessment."""

    reason: str | None = None
    """Optional explanation of availability, missing dependencies, or assessment 
    failure."""

    runtime: str | None = None
    """Runtime in which availability was assessed; required for completed 
    assessments."""

    scope: _JsonObject = Field(default_factory=dict)
    """Non-secret assessment scope, such as return type and configuration revision."""

    @model_validator(mode="after")
    def _check_assessment(self) -> "ResourceCapability":
        if self.state != "unknown" and not self.runtime:
            raise ValueError("A completed capability assessment requires a runtime")
        if self.state == "available" and not self.candidates:
            raise ValueError("An available capability requires at least one candidate")
        return self


class ResourceCapabilities(BaseModel):
    """Independent opener and preview availability for one resource."""

    model_config = _SNAPSHOT_CONFIG

    opener: ResourceCapability = Field(default_factory=ResourceCapability)
    """Availability of candidate data openers in the assessed runtime."""

    preview: ResourceCapability = Field(default_factory=ResourceCapability)
    """Availability of preview actions, assessed independently of data openers."""


class OutputDiscoveryState(BaseModel):
    """Discovery state for an output, including outputs without resource rows."""

    model_config = _SNAPSHOT_CONFIG

    discovery_state: DiscoveryState = "unresolved"
    """Completion of the requested discovery view for this output."""

    diagnostics: tuple[ResourceDiagnostic, ...] = ()
    """Output-level diagnostics, including when discovery yields no resource rows."""


def make_resource_id(output_name: str, *ancestry: str) -> str:
    """Encode stable output/ancestry identities, never effective access URLs.

    The versioned selector is opaque to callers and unique within a job view.
    Resolvers supply all relevant owners, including Collection identity and
    configured entry identity. Encoding components separately prevents path
    separator collisions and permits arbitrary Unicode names.
    """
    encoded = json.dumps(
        [output_name, *ancestry], ensure_ascii=False, separators=(",", ":")
    )
    return "jr1." + base64.urlsafe_b64encode(encoded.encode("utf-8")).decode().rstrip(
        "="
    )


class JobResultResource(BaseModel):
    """One selectable job result, with portable ownership and access metadata.

    Fields and nested JSON metadata are read-only snapshots. JSON arrays become
    tuples in Python and serialize back to arrays. ``has_value`` distinguishes
    an omitted value from a present null; serialization preserves that distinction.
    ``link`` is an isolated, frozen ``gavicore.models.Link``. Original job output
    and schema information belong in ``provenance``, separately from the selected
    link/value and format. Opening services and resolved credentials stay outside
    this model; ``access`` and ``open_hints`` contain only non-secret descriptions.
    """

    model_config = _SNAPSHOT_CONFIG

    schema_version: Literal[1] = 1
    """Version of the portable resource description's JSON schema."""

    id: str = Field(min_length=1)
    """Opaque selector unique within the job view and stable across URL renewal."""

    output_name: str = Field(min_length=1)
    """Name of the original process output that owns this resource."""

    parent_id: str | None = None
    """Selector of the immediate owner, which may be absent from the loaded view."""

    path: str = ""
    """Human-readable output and ancestor path for inspection and display."""

    item_id: str | None = None
    """Source STAC Item identifier, when applicable; it is not globally unique."""

    kind: str = Field(min_length=1)
    """Extensible semantic kind, such as ``value``, ``link``, ``stac-item``, or 
    ``asset``."""

    key: str | None = None
    """Local source identifier, such as an Asset key or Item identifier."""

    link: Link | None = None
    """Normalized, frozen access Link; absent for resources without their own URL."""

    value: _JsonValue = None
    """Selected inline or qualified value; use ``has_value`` 
    to distinguish absent from null."""

    media_type: str | None = None
    """Effective representation media type, retaining parameters; not a Python 
    return type."""

    title: str | None = None
    """Optional display title; ``display_title`` supplies a key or ID fallback."""

    description: str | None = None
    """Optional human-readable description of the selected resource."""

    roles: tuple[str, ...] = ()
    """Advertised roles, such as ``data`` or ``thumbnail``; empty means unspecified."""

    metadata: _JsonObject = Field(default_factory=dict)
    """Read-only source metadata, including STAC identity, format, 
    and ownership facts."""

    provenance: _JsonObject = Field(default_factory=dict)
    """Original job/output/schema context and derivation history, 
    separate from access location."""

    open_hints: _JsonObject = Field(default_factory=dict)
    """Non-secret defaults scoped to opener identifiers, 
    subject to adapter validation."""

    access: _JsonObject = Field(default_factory=dict)
    """Non-secret storage and authentication requirements; 
    excludes resolved credentials."""

    capabilities: ResourceCapabilities = Field(default_factory=ResourceCapabilities)
    """Independent runtime snapshots of opener and preview availability."""

    discovery_state: DiscoveryState = "unresolved"
    """State of this resource's semantic expansion, 
    independent of opener availability."""

    diagnostics: tuple[ResourceDiagnostic, ...] = ()
    """Resource-level detection, validation, access, or traversal explanations."""

    @property
    def has_value(self) -> bool:
        """Whether a selected value is present, including an explicit null."""
        return "value" in self.model_fields_set

    @property
    def display_title(self) -> str:
        """Title with the local key, then opaque ID, as fallbacks."""
        return self.title or self.key or self.id

    def with_updates(self, **changes: Any) -> "JobResultResource":
        """Return a validated snapshot without modifying this resource.

        Use this instead of Pydantic's unvalidated ``model_copy(update=...)``
        when enriching or rewriting descriptions in a transformer.
        """
        return type(self).model_validate(self.model_dump(by_alias=True) | changes)

    @field_validator("link")
    @classmethod
    def _snapshot_link(cls, link: Link | None) -> Link | None:
        if link is None:
            return None
        return _ResourceLink.model_validate(
            link.model_dump(by_alias=True, exclude_unset=True)
        )

    @field_serializer("link")
    def _serialize_link(self, link: Link | None, info: SerializationInfo) -> Any:
        if link is None:
            return None
        return link.model_dump(
            by_alias=True,
            **_serialization_options(info),
        )

    @model_serializer(mode="wrap")
    def _serialize(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> dict[str, Any]:
        data = handler(self)
        if not self.has_value:
            data.pop("value", None)
        elif self.value is None:
            included = info.include is None or "value" in info.include
            excluded = info.exclude is not None and "value" in info.exclude
            if included and not excluded:
                data["value"] = None
        return data


class ResourceNotFoundError(LookupError):
    """No currently loaded resource matches the supplied selection criteria."""


class AmbiguousResourceError(ValueError):
    """Several currently loaded resources match the supplied criteria."""


class JobResultResourceListing(BaseModel):
    """A portable snapshot of loaded resources, discovery states, and diagnostics.

    Selection, positional access, iteration, length, and rendering are local:
    they never fetch metadata, follow continuations, or assess capabilities.
    ``continuation`` is an opaque token for a separate client request. Its scope
    and lifetime are enforced by discovery, not by this description. A complete
    requested view may contain containers whose own expansion is unresolved.
    Original ``JobResults`` remain separate from this derived listing.
    """

    model_config = _SNAPSHOT_CONFIG

    schema_version: Literal[1] = 1
    """Version of the portable listing description's JSON schema."""

    resources: tuple[JobResultResource, ...] = ()
    """Currently loaded resources; iteration and indexing never load additional rows."""

    discovery_state: DiscoveryState = "unresolved"
    """Completion of the requested view, independent of deferred container expansion."""

    continuation: str | None = None
    """Opaque token for an explicit client continuation request, 
    or ``None`` if absent."""

    diagnostics: tuple[ResourceDiagnostic, ...] = ()
    """Listing-level discovery explanations, including limits and partial failures."""

    output_states: Mapping[str, OutputDiscoveryState] = Field(default_factory=dict)
    """Read-only states for requested outputs, including empty and failed outputs."""

    @field_validator("output_states")
    @classmethod
    def _freeze_output_states(
        cls, states: Mapping[str, OutputDiscoveryState]
    ) -> Mapping[str, OutputDiscoveryState]:
        return MappingProxyType(dict(states))

    @field_serializer("output_states")
    def _serialize_output_states(
        self, states: Mapping[str, OutputDiscoveryState]
    ) -> dict:
        return dict(states)

    @model_validator(mode="after")
    def _unique_ids(self) -> "JobResultResourceListing":
        ids = [resource.id for resource in self.resources]
        if len(ids) != len(set(ids)):
            raise ValueError("Loaded resource IDs must be unique")
        return self

    def __iter__(self) -> Iterator[JobResultResource]:  # type: ignore[override]
        """Iterate over loaded resources without fetching more rows."""
        return iter(self.resources)

    def __len__(self) -> int:
        """Return the number of loaded resources."""
        return len(self.resources)

    @overload
    def __getitem__(self, index: int) -> JobResultResource: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[JobResultResource, ...]: ...

    def __getitem__(
        self, index: int | slice
    ) -> JobResultResource | tuple[JobResultResource, ...]:
        """Return a loaded resource, or a tuple of loaded resources for a slice."""
        return self.resources[index]

    def select(self, **criteria: str | None) -> JobResultResource:
        """Select exactly one loaded row by ID, output name, Item ID, or key.

        Raises ``ResourceNotFoundError`` or ``AmbiguousResourceError``. A match
        does not claim uniqueness across unloaded pages; use an opaque ID for
        an exact selection. Unsupported criteria raise ``TypeError``.
        """
        unknown = criteria.keys() - {"id", "output_name", "item_id", "key"}
        if unknown:
            raise TypeError(
                f"Unsupported resource selection criteria: {sorted(unknown)}"
            )
        matches = [
            resource
            for resource in self.resources
            if all(getattr(resource, name) == value for name, value in criteria.items())
        ]
        if not matches:
            raise ResourceNotFoundError(f"No loaded resource matches {criteria!r}")
        if len(matches) != 1:
            raise AmbiguousResourceError(
                f"{len(matches)} loaded resources match {criteria!r}; select by ID "
                "or include output and Item ownership"
            )
        return matches[0]

    def __str__(self) -> str:
        """Render loaded metadata and discovery notices as plain text."""
        rows = [_HEADINGS, *_listing_rows(self)]
        widths = [max(len(row[i]) for row in rows) for i in range(len(_HEADINGS))]
        table = [
            " | ".join(
                cell.ljust(width) for cell, width in zip(row, widths, strict=True)
            )
            for row in rows
        ]
        return "\n".join([*_listing_notices(self), *table])

    def __repr__(self) -> str:
        """Use the same readable table as the plain-text display."""
        return str(self)

    def _repr_html_(self) -> str:
        """Render escaped loaded metadata without optional readers or I/O."""
        notices = "".join(
            f"<p>{escape(notice)}</p>" for notice in _listing_notices(self)
        )
        headings = "".join(f"<th>{escape(heading)}</th>" for heading in _HEADINGS)
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
            for row in _listing_rows(self)
        )
        return (
            notices + f"<table><thead><tr>{headings}</tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )


_HEADINGS = (
    "Output",
    "Item/path",
    "Key",
    "Title",
    "Roles",
    "Format",
    "Opener",
    "Preview",
    "Discovery",
)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_json(item) for item in value]
    return value


class _ResourceLink(Link):
    """An isolated, read-only OGC Link inside a resource snapshot."""

    model_config = ConfigDict(
        frozen=True, hide_input_in_errors=True, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def _freeze(self) -> "_ResourceLink":
        object.__setattr__(
            self, "options", _freeze_json(_json_adapter.validate_python(self.options))
        )
        object.__setattr__(
            self,
            "__pydantic_extra__",
            _freeze_json(_json_adapter.validate_python(self.model_extra or {})),
        )
        return self

    @model_serializer
    def _serialize(self, info: SerializationInfo) -> dict[str, Any]:
        data = {}
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if info.exclude_none and value is None:
                continue
            if info.exclude_unset and name not in self.model_fields_set:
                continue
            if info.exclude_defaults and value == field.default:
                continue
            data[name] = _thaw_json(value)
        data.update(
            (name, _thaw_json(value))
            for name, value in (self.model_extra or {}).items()
            if not info.exclude_none or value is not None
        )
        data = _json_adapter.dump_python(data, **_serialization_options(info))
        if info.by_alias and "options" in data:
            data["x-options"] = data.pop("options")
        return data


def _serialization_options(info: SerializationInfo) -> dict[str, Any]:
    # Pydantic's serializer and dump APIs use different recursive filter types.
    return {
        "mode": info.mode,
        "include": info.include,
        "exclude": info.exclude,
        "exclude_none": info.exclude_none,
        "exclude_defaults": info.exclude_defaults,
        "exclude_unset": info.exclude_unset,
    }


def _capability_text(capability: ResourceCapability) -> str:
    text: str = capability.state
    if capability.candidates:
        text += " (" + ", ".join(action.title for action in capability.candidates) + ")"
    if capability.reason:
        text += f": {capability.reason}"
    return text


def _listing_notices(listing: JobResultResourceListing) -> list[str]:
    notices = [
        f"Discovery: {listing.discovery_state}; loaded resources: {len(listing)}"
    ]
    if not listing.resources:
        notices.append("No resources loaded.")
    if listing.continuation is not None:
        notices.append("Another page is available; request continuation explicitly.")
    for name, state in listing.output_states.items():
        notices.append(f"Output {name}: {state.discovery_state}")
        notices.extend(f"{d.code}: {d.message}" for d in state.diagnostics)
    notices.extend(f"{d.code}: {d.message}" for d in listing.diagnostics)
    for resource in listing.resources:
        notices.extend(
            f"{resource.id}: {d.code}: {d.message}" for d in resource.diagnostics
        )
    return notices


def _listing_rows(listing: JobResultResourceListing) -> list[tuple[str, ...]]:
    return [
        (
            resource.output_name,
            resource.path or resource.item_id or "unspecified",
            resource.key if resource.key is not None else "unspecified",
            resource.display_title,
            ", ".join(resource.roles) or "unspecified",
            resource.media_type or "unspecified",
            _capability_text(resource.capabilities.opener),
            _capability_text(resource.capabilities.preview),
            resource.discovery_state,
        )
        for resource in listing.resources
    ]
