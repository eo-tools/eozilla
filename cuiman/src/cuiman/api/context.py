#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Shared job-result operation context, separate from portable resources."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import TYPE_CHECKING, Any, Final, Protocol

from gavicore.models import JobResults, OutputDescription, ProcessDescription

from .metadata import DiscoveryLimits, MetadataLoader
from .resources import JobResultResource, ResourceDiagnostic

if TYPE_CHECKING:
    from .config import ClientConfig
    from .opener.opener import JobResultOpener


class ResourceAccessProvider(Protocol):
    """Resolve storage options only when opening an authorized selected target.

    This connects readers to the application's credential policy while keeping
    credentials out of portable resource descriptions and discovery operations.
    Providers must enforce target/endpoint scope using local policy. Resource
    provenance and remote access descriptions do not authorize credentials.
    Process API authentication is never forwarded automatically.
    """

    async def resolve(self, resource: JobResultResource) -> Mapping[str, Any]:
        """Return storage settings and credentials needed to read this exact target.

        Called by the context at read time, after an opener accepts the resource.
        """
        ...


@dataclass(frozen=True)
class JobResultContext:
    """Shared inputs, configuration, and services for job-result operations.

    A context carries the application objects and preferences that portable
    resource descriptions cannot carry. Sharing it across discovery and opening
    lets extensions reuse one loader and configuration without separate context
    interfaces for each operation.
    Discovery supplies an original output name/value and may use a bounded
    metadata loader. Opening supplies client configuration and a selected
    resource separately; original output facts never replace that resource.
    Credential acquisition belongs only to reading. Candidate contexts retain
    shared services while isolating their effective options. Resolvers must not
    mutate original values or process metadata. Fields are frozen; candidate
    reader options remain independent mutable mappings.
    """

    output_name: str = ""
    """Original output identifier for discovery; empty for opening-only contexts."""
    value: Any = field(default_factory=lambda: _UNSET, repr=False)
    """Original output for discovery; omitted and explicitly supplied null are distinct."""
    job_id: str | None = None
    """Producing job identity, when supplied by the client."""
    service_url: str | None = None
    """Producing service identity; never authorization to forward credentials."""
    base_uri: str | None = None
    """Containing result document URI for resolving relative output references."""
    output_description: OutputDescription | None = None
    """Original output/schema facts for detection and provenance, not selected format."""
    process_description: ProcessDescription | None = None
    """Producing process description for process-scoped discovery and provenance."""
    loader: MetadataLoader | None = None
    """Shared bounded metadata loader; never used to fetch Asset payloads."""
    limits: DiscoveryLimits = field(default_factory=DiscoveryLimits)
    """Discovery limits; a supplied loader's limits take precedence."""
    stac_hint: bool = False
    """Explicit STAC candidate hint permitting a bounded metadata probe."""
    config: "ClientConfig | None" = field(default=None, repr=False, kw_only=True)
    """Receiving client configuration; optional for standalone discovery extensions."""
    data_type: type | None = None
    """Requested Python return type; candidates must respect it."""
    media_type: str | None = None
    """Call override, applied without changing the resource's advertised format."""
    options: dict[str, Any] = field(default_factory=dict, repr=False)
    """Candidate reader arguments; may contain runtime credentials and are not serialized."""
    option_sources: dict[str, str] = field(default_factory=dict)
    """Top-level provenance of effective settings, without their values."""
    diagnostics: tuple[ResourceDiagnostic, ...] = ()
    """Rejected producer hint explanations, containing no credential values."""

    def __post_init__(self) -> None:
        if not self.output_name and self.config is None:
            raise ValueError("An output name or client configuration is required")
        if self.loader is not None:
            object.__setattr__(self, "limits", self.loader.limits)

    def require_output(self) -> None:
        """Check that an opening-only context is ready for discovery before I/O.

        Discovery needs the original output name and value; explicit null is
        valid, whereas an omitted value is not.
        """
        if not self.output_name:
            raise ValueError("An output name is required for discovery")
        if self.value is _UNSET:
            raise ValueError("An output value is required for discovery")

    @property
    def non_secret_options(self) -> dict[str, Any]:
        """Independent effective settings with storage/authentication secrets omitted.

        Read alongside ``option_sources`` to inspect candidate settings. Custom
        adapters with additional secret option names must extend this filtering
        before displaying their settings.
        """
        return _without_credentials(self.options)

    def media_type_for(self, resource: JobResultResource) -> str | None:
        """Choose the format an opener should use to assess and read this resource.

        An explicit call override wins over the selected resource's advertised
        media type. Parameters are retained and the resource remains unchanged.
        """
        return self.media_type if self.media_type is not None else resource.media_type

    def for_opener(
        self, resource: JobResultResource, opener: "JobResultOpener"
    ) -> "JobResultContext":
        """Validate hints and resolve defaults/configuration/caller precedence.

        Return a candidate context so one opener's settings cannot affect another
        candidate or the caller. Shared configuration and metadata services are
        retained while effective reader options are copied independently.
        Only mappings declared mergeable by the opener are merged. Other values
        replace inherited values; supplying ``None`` clears an inherited setting.
        No credentials or payloads are acquired here.
        """
        identifier = opener.identifier()
        wire = resource.model_dump(mode="json")
        hints = (
            dict(wire.get("link", {}).get("x-options", {}) or {})
            if wire.get("link")
            else {}
        )
        scoped = wire["open_hints"].get(identifier, {})
        hints, rejected = opener.validate_hints(hints)
        diagnostics: tuple[ResourceDiagnostic, ...] = ()
        if isinstance(scoped, dict):
            scoped, scoped_rejected = opener.validate_hints(scoped)
            rejected = (*rejected, *scoped_rejected)
        else:
            diagnostics = (
                ResourceDiagnostic(
                    code="invalid-open-hints", message="Opener hints must be an object"
                ),
            )
            scoped = {}
        options: dict[str, Any] = {}
        sources: dict[str, str] = {}
        for source, layer in (
            ("default", opener.default_options(resource, context=self)),
            ("resource", hints),
            ("resource", scoped),
            (
                "config",
                self.config.get_job_result_opener_options(resource, identifier)
                if self.config is not None
                else {},
            ),
            ("caller", self.options),
        ):
            if opener.storage_in_backend:
                layer = _backend_storage_layer(layer, opener.mergeable_options)
            options = _merge_options(options, layer, opener.mergeable_options)
            sources.update({key: source for key in layer})
        return replace(
            self,
            options=options,
            option_sources=sources,
            diagnostics=(*diagnostics, *rejected),
        )

    async def reader_options(
        self, resource: JobResultResource, *, storage_in_backend: bool = False
    ) -> dict[str, Any]:
        """Resolve scoped storage access at read time, keeping credential sets atomic.

        This is the handoff from describing a resource to accessing its data:
        readers receive usable settings while the portable resource stays free
        of resolved credentials.
        Explicit caller credentials suppress provider acquisition. For xarray,
        storage arguments are placed under ``backend_kwargs``. Returned options
        are independent; they never change resources or caller inputs.
        """
        options = deepcopy(self.options)
        backend = options.get("backend_kwargs") or {}
        storage = options.pop("storage_options", {}) or {}
        if storage_in_backend:
            storage = _merge_options(
                backend.get("storage_options") or {},
                storage,
                frozenset({"client_kwargs"}),
            )
        provider = (
            self.config.job_result_access_provider if self.config is not None else None
        )
        if provider is not None and not (_CREDENTIAL_KEYS & storage.keys()):
            supplied = dict(await provider.resolve(resource))
            storage = _merge_options(supplied, storage, frozenset({"client_kwargs"}))
        if storage:
            if storage_in_backend:
                options["backend_kwargs"] = dict(backend) | {"storage_options": storage}
            else:
                options["storage_options"] = storage
        return options


async def describe_job_output(
    job_id: str,
    results: JobResults,
    output_name: str | None,
    *,
    service_url: str | None = None,
    process_description: ProcessDescription | None = None,
    context: JobResultContext | None = None,
) -> JobResultResource:
    """Describe one original output for the job-ID form of ``open_job_result()``.

    This adapts job results to the same resource-based reader dispatch used for
    explicitly selected resources. It selects an output by name, or requires
    exactly one output when no name is given, and uses the generic value resolver
    without STAC expansion or metadata I/O.
    """
    from .opener.errors import JobResultOpenError
    from .resolver.impl import ValueResolver

    mapping = results.root or {}
    if output_name is None:
        if len(mapping) != 1:
            raise JobResultOpenError(
                "Specify output_name: job results do not contain exactly one output"
            )
        output_name = next(iter(mapping))
    if output_name not in mapping:
        raise JobResultOpenError(f"Job output {output_name!r} was not found")
    descriptions = process_description.outputs if process_description else None
    ctx = replace(
        context or JobResultContext(output_name, mapping[output_name]),
        output_name=output_name,
        value=mapping[output_name],
        job_id=job_id,
        service_url=service_url,
        process_description=process_description,
        output_description=descriptions.get(output_name)
        if isinstance(descriptions, dict)
        else None,
    )
    return (await ValueResolver().resolve(ctx))[0]


class _Unset(Enum):
    VALUE = "not supplied"


_UNSET: Final[_Unset] = _Unset.VALUE
_CREDENTIAL_KEYS = frozenset(
    {
        "key",
        "secret",
        "token",
        "access_key",
        "secret_key",
        "session_token",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "password",
    }
)
_SECRET_OPTIONS = _CREDENTIAL_KEYS | {
    "auth",
    "headers",
    "cookies",
    "credentials",
    "credential",
    "client_secret",
    "sas_token",
    "account_key",
    "connection_string",
}


def _validate_open_arguments(
    job_id: str | JobResultResource,
    output_name: str | None | _Unset,
    poll_interval: float | _Unset,
    timeout: float | _Unset,
    *,
    default_poll: float,
    default_timeout: float,
) -> tuple[str | None, float, float]:
    if not isinstance(job_id, (str, JobResultResource)):
        raise TypeError("job_id must be a string or JobResultResource")
    if isinstance(job_id, JobResultResource):
        supplied = [
            name
            for name, value in (
                ("output_name", output_name),
                ("poll_interval", poll_interval),
                ("timeout", timeout),
            )
            if value is not _UNSET
        ]
        if supplied:
            raise TypeError(
                f"Job-only arguments cannot be supplied with a resource: {', '.join(supplied)}"
            )
    return (
        None if isinstance(output_name, _Unset) else output_name,
        default_poll if isinstance(poll_interval, _Unset) else poll_interval,
        default_timeout if isinstance(timeout, _Unset) else timeout,
    )


def _merge_options(
    lower: Mapping[str, Any], higher: Mapping[str, Any], mergeable: frozenset[str]
) -> dict[str, Any]:
    result = deepcopy(dict(lower))
    if _CREDENTIAL_KEYS & higher.keys():
        for key in _CREDENTIAL_KEYS:
            result.pop(key, None)
    for key, value in higher.items():
        if (
            key in mergeable
            and isinstance(value, Mapping)
            and isinstance(result.get(key), Mapping)
        ):
            result[key] = _merge_options(result[key], value, mergeable)
        else:
            result[key] = deepcopy(value)
    return result


def _backend_storage_layer(
    layer: Mapping[str, Any], mergeable: frozenset[str]
) -> dict[str, Any]:
    result = deepcopy(dict(layer))
    if "storage_options" in result:
        storage = result.pop("storage_options")
        backend = result.get("backend_kwargs") or {}
        result["backend_kwargs"] = _merge_options(
            backend, {"storage_options": storage}, mergeable
        )
    return result


def _without_credentials(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_credentials(setting)
            for key, setting in value.items()
            if not isinstance(key, str) or key.lower() not in _SECRET_OPTIONS
        }
    if isinstance(value, (tuple, list)):
        return [_without_credentials(setting) for setting in value]
    return deepcopy(value)
