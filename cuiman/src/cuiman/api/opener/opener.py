#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""One resource-based contract and dispatch path for all job result openers."""

import warnings
from abc import ABC, abstractmethod
from collections.abc import Mapping
from inspect import isclass
from typing import Any, ClassVar

from ..context import JobResultContext
from ..exceptions import ClientWarning
from ..resources import JobResultResource, ResourceDiagnostic
from .errors import JobResultOpenError


class JobResultOpener(ABC):
    """Open one authoritative resource using receiving-client runtime settings.

    An opener adapts the common resource description to a Python reader, such as
    xarray or pandas. It handles the selected target's format and return type;
    discovery has already decided which resource the caller wants.
    Acceptance respects the requested return type without payload I/O or access
    acquisition. Original job outputs and schemas are provenance only. Producer
    options require this opener's validation; caller options are locally trusted.
    """

    id: ClassVar[str | None] = None
    """Stable identifier for scoped hints; defaults to the qualified class name."""
    hint_types: ClassVar[Mapping[str, type | tuple[type, ...]]] = {}
    """Accepted producer option names and value types; undeclared hints are rejected."""
    mergeable_options: ClassVar[frozenset[str]] = frozenset()
    """Mapping options merged by key; other values replace, and None clears inheritance."""
    storage_in_backend: ClassVar[bool] = False
    """Whether storage_options is an alias for backend_kwargs.storage_options."""

    @classmethod
    def identifier(cls) -> str:
        """Identify this reader when applying scoped hints and client overrides.

        Use an explicit ``id`` or fall back to the qualified class name.
        """
        return cls.id or f"{cls.__module__}.{cls.__qualname__}"

    @classmethod
    def is_usable(cls) -> bool:
        """Let dispatch skip readers unavailable in the current environment.

        Check dependencies or other local requirements without resource access.
        """
        return True

    @abstractmethod
    async def accept(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> bool:
        """Tell dispatch whether this reader can handle the selected description.

        Respect the requested return type without reading data or acquiring
        credentials. Acceptance identifies a candidate, not verified access.
        """

    @abstractmethod
    async def open(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> Any:
        """Read the accepted resource and return its Python representation.

        Use the candidate context's effective options and acquire scoped storage
        access as needed; do not select a different target or repeat discovery.
        """

    def default_options(
        self, resource: JobResultResource, *, context: JobResultContext
    ) -> dict[str, Any]:
        """Supply format-specific defaults before hints and user settings apply.

        Translate recognized resource metadata to non-secret reader options;
        subsequent option layers can override these defaults.
        """
        return {}

    def validate_hints(
        self, hints: Mapping[str, Any]
    ) -> tuple[dict[str, Any], tuple[ResourceDiagnostic, ...]]:
        """Validate declared types and non-secret storage/backend metadata.

        This is the boundary between producer-supplied suggestions and effective
        reader options. Return accepted hints and diagnostics for rejected ones.
        Remote endpoints and credentials require locally scoped access policy.
        Override to implement a richer reader-specific producer option schema.
        """
        accepted: dict[str, Any] = {}
        diagnostics = []
        for key, value in hints.items():
            expected = self.hint_types.get(key)
            if (
                expected is not None
                and isinstance(value, expected)
                and _valid_hint(key, value)
            ):
                accepted[key] = value
            else:
                diagnostics.append(
                    ResourceDiagnostic(
                        code="unsupported-open-hint",
                        message=f"Rejected reader hint {key!r}",
                    )
                )
        return accepted, tuple(diagnostics)


async def open_job_result(
    resource: JobResultResource,
    *opener_types: type[JobResultOpener],
    context: JobResultContext,
) -> Any:
    """Try ordered candidates with independent effective runtime options.

    Both client opening forms use this dispatch path: an original job output
    normalized to a resource and an explicitly selected resource. Return the
    first successful reader's Python object.
    Group opening failures after all accepting candidates fail. Warnings and
    diagnostics report error types without runtime option values. Cancellation
    propagates; no lookup or rediscovery is performed here.
    """
    errors: list[tuple[type[JobResultOpener], Exception]] = []
    accepted_count = 0
    for opener_type in opener_types:
        assert_opener_type_valid(opener_type)
        try:
            if not opener_type.is_usable():
                continue
            opener = opener_type()
            candidate = context.for_opener(resource, opener)
            accepted = await opener.accept(resource, context=candidate)
        except Exception as exc:
            _warn(opener_type, exc)
            continue
        if accepted:
            accepted_count += 1
            try:
                return await opener.open(resource, context=candidate)
            except Exception as exc:
                errors.append((opener_type, exc))
    if not errors:
        raise JobResultOpenError(
            "No job result opener found"
            if opener_types
            else "No job result openers provided"
        )
    summary = "\n".join(
        f"* {opener_type.__name__}: {type(exc).__name__}" for opener_type, exc in errors
    )
    raise JobResultOpenError(
        f"Job result opener failure:\n{summary}"
    ) from ExceptionGroup(
        f"{len(errors)} of {accepted_count} possible opener{'' if accepted_count == 1 else 's'} failed",
        [exc for _, exc in errors],
    )


def assert_opener_type_valid(opener_type: type[JobResultOpener]) -> None:
    """Reject entries that are not opener subclasses."""
    if not isclass(opener_type) or not issubclass(opener_type, JobResultOpener):
        raise TypeError(
            f"Type compatible with {JobResultOpener.__name__} expected, but got {opener_type}"
        )


def _warn(opener_type: type[JobResultOpener], error: Exception) -> None:
    warnings.warn(
        f"Unexpected error occurred in {opener_type.__name__}: {type(error).__name__}",
        category=ClientWarning,
        stacklevel=2,
    )


def _valid_hint(key: str, value: Any) -> bool:
    if key == "storage_options":
        allowed = {"anon": bool, "default_fill_cache": bool, "use_listings_cache": bool}
        return all(
            name in allowed and isinstance(setting, allowed[name])
            for name, setting in value.items()
        )
    if key == "backend_kwargs":
        allowed_backend: dict[str, type | tuple[type, ...]] = {
            "consolidated": (bool, type(None)),
            "group": (str, type(None)),
            "storage_options": dict,
        }
        return all(
            name in allowed_backend
            and isinstance(setting, allowed_backend[name])
            and (name != "storage_options" or _valid_hint(name, setting))
            for name, setting in value.items()
        )
    if key == "engine":
        return value in {"zarr", "netcdf4", "h5netcdf", "scipy", "rasterio"}
    return True
