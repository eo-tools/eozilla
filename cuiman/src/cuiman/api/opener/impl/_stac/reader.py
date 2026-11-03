# Copyright (c) 2026 by the Eozilla team and contributors
# Permissions are hereby granted under the terms of the Apache 2.0 License:
# https://opensource.org/license/apache-2-0.

"""Validated Asset hints and scoped runtime options for built-in readers."""

import warnings
from copy import deepcopy
from dataclasses import replace
from inspect import isawaitable
from typing import Any
from urllib.parse import urlsplit

from cuiman.api.assets import as_stac_asset
from cuiman.api.exceptions import ClientWarning
from cuiman.api.opener.context import JobResultOpenContext, _copy_options
from cuiman.api.opener.errors import JobResultOpenError

_XARRAY = "https://stac-extensions.github.io/xarray-assets/v1.0.0/schema.json"
_STORAGE_V1 = "https://stac-extensions.github.io/storage/v1.0.0/schema.json"
_STORAGE_V2 = "https://stac-extensions.github.io/storage/v2.0.0/schema.json"
# Only these option dictionaries merge recursively; other values replace whole.
_MAPPINGS = {
    "chunks",
    "backend_kwargs",
    "storage_options",
    "client_kwargs",
    "config_kwargs",
}
# Any of these keys signals an explicit choice of identity or authentication.
_CREDENTIALS = {
    "key",
    "secret",
    "token",
    "anon",
    "profile",
    "session",
    "username",
    "password",
}
_ALIASES = {
    "aws_access_key_id": "key",
    "aws_secret_access_key": "secret",
    "aws_session_token": "token",
}


async def prepare_asset_reader(
    ctx: JobResultOpenContext, opener_id: str
) -> JobResultOpenContext:
    """Prepare options and optional S3 access for an already accepted Asset.

    Merge reader defaults, validated producer hints, client overrides, and
    caller options in increasing precedence. Client/caller options are trusted;
    producer hints are limited to the supported schema. An access provider can
    supply credentials when neither trusted layer explicitly controls access.

    Return a context copy containing effective reader options. Also update the
    input context's redacted ``resolved_options`` and ``option_sources`` for
    diagnostics; never modify the original Asset or its option dictionaries.
    """
    asset = as_stac_asset(ctx.value)
    assert asset is not None
    defaults: dict[str, Any] = {}
    # Media type is authoritative; inspect the URL suffix only when it is absent.
    if opener_id == "xarray" and (
        (ctx.output_media_type or "").split(";", 1)[0].strip().lower()
        in {"application/zarr", "application/x-zarr", "application/vnd+zarr", "application/vnd.zarr"}
        or not ctx.output_media_type
        and urlsplit(ctx.location or "").path.rstrip("/").lower().endswith(".zarr")
    ):
        defaults = {"engine": "zarr"}
    # Give application callbacks their own options so edits cannot affect callers.
    callback_ctx = replace(ctx, options=_copy_options(ctx.options))
    factory = type(ctx.config).asset_reader_options
    overrides = factory(callback_ctx, opener_id) if factory else {}
    if not isinstance(overrides, dict):
        raise JobResultOpenError("Asset reader overrides must be a mapping")
    caller = _normalize(ctx.options, opener_id)
    client = _normalize(overrides, opener_id)
    effective: dict[str, Any] = {}
    sources: dict[str, str] = {}
    # Later layers override earlier ones; sources records provenance per leaf.
    for label, layer in (
        ("reader-default", defaults),
        (
            "producer",
            _producer_hints(
                asset,
                opener_id,
                ctx.location or "",
                ctx.output_media_type,
                ctx.asset_alternate,
            ),
        ),
        ("client", client),
        ("caller", caller),
    ):
        effective = _merge(effective, layer, sources, label)
    # The access provider sees the resolved policy, with credentials removed.
    ctx.resolved_options = _non_secret(effective)
    ctx.option_sources = {
        path: source
        for path, source in sources.items()
        if _has_path(ctx.resolved_options, path)
    }
    storage = _storage(effective, opener_id)
    # Explicit clearing and trusted credentials control access without invoking
    # a provider. A replacement always discards old tokens as well as old keys.
    controls = any(_controls_access(layer, opener_id) for layer in (client, caller))
    provider = type(ctx.config).asset_access_provider
    if (ctx.location or "").startswith("s3://") and provider and not controls:
        access_ctx = replace(ctx, options=deepcopy(ctx.resolved_options))
        access = provider(access_ctx, opener_id)
        if isawaitable(access):
            access = await access
        if access is not None:
            if not isinstance(access, dict):
                raise JobResultOpenError(
                    "Asset access provider must return a mapping or None"
                )
            provided = _normalize({"storage_options": access}, opener_id)
            access_sources: dict[str, str] = {}
            # Record provider provenance separately before merging its defaults.
            _merge({}, provided, access_sources, "access-provider")
            # Trusted reader overrides still take precedence over provider defaults.
            effective = _merge(provided, effective, {}, "reader")
            sources = {**access_sources, **sources}
            storage = _storage(effective, opener_id)
    if storage is not None and not isinstance(storage, dict):
        raise JobResultOpenError("Asset storage options must be a mapping or None")
    # Refresh diagnostics after acquiring access, keeping secret options only in
    # the returned execution context. Drop provenance for redacted leaves.
    ctx.resolved_options = _non_secret(effective)
    ctx.option_sources = {
        path: source
        for path, source in sources.items()
        if _has_path(ctx.resolved_options, path)
    }
    return replace(ctx, options=effective)


def _normalize(options: dict[str, Any], opener_id: str) -> dict[str, Any]:
    """Copy options into the reader's argument shape and normalize AWS aliases.

    Xarray expects storage and consolidation options under ``backend_kwargs``;
    top-level aliases override corresponding nested values. Other readers keep
    storage options at the top level. Explicit None values remain meaningful.
    """
    result = _copy_options(options)
    if opener_id == "xarray":
        backend = result.get("backend_kwargs")
        if backend is not None and not isinstance(backend, dict):
            raise JobResultOpenError("Asset backend options must be a mapping or None")
        if isinstance(backend, dict) and isinstance(
            backend.get("storage_options"), dict
        ):
            _normalize_credentials(backend["storage_options"])
        if "consolidated" in result:
            if backend is None:
                backend = result["backend_kwargs"] = {}
            backend["consolidated"] = result.pop("consolidated")
        if "storage_options" in result:
            storage = result.pop("storage_options")
            if isinstance(storage, dict):
                _normalize_credentials(storage)
            if backend is None:
                backend = result["backend_kwargs"] = {}
            # Merge mappings, but let an explicit None clear nested settings.
            backend["storage_options"] = (
                _merge(
                    {"storage_options": backend.get("storage_options") or {}},
                    {"storage_options": storage},
                    {},
                    "alias",
                )["storage_options"]
                if isinstance(storage, dict)
                else storage
            )
        holder = backend
    else:
        holder = result
    if isinstance(holder, dict) and isinstance(holder.get("storage_options"), dict):
        _normalize_credentials(holder["storage_options"])
    return result


def _normalize_credentials(storage: dict[str, Any]) -> None:
    """Normalize AWS credential aliases in a copied storage mapping in place.

    Preserve existing canonical keys, including when moving credentials out of
    ``client_kwargs`` into the location expected by the filesystem reader.
    """
    for old, new in _ALIASES.items():
        if old in storage:
            storage.setdefault(new, storage.pop(old))
    client = storage.get("client_kwargs")
    if isinstance(client, dict):
        for old, new in _ALIASES.items():
            if old in client:
                storage.setdefault(new, client.pop(old))
        if not client:
            storage.pop("client_kwargs")


def _storage(options: dict[str, Any], opener_id: str) -> Any:
    """Extract storage options from the reader-specific nesting for validation."""
    holder = options.get("backend_kwargs") if opener_id == "xarray" else options
    return holder.get("storage_options") if isinstance(holder, dict) else None


def _controls_access(options: dict[str, Any], opener_id: str) -> bool:
    """Check whether a trusted layer supplies authentication or clears access.

    Explicit None for storage options (or xarray backend kwargs) suppresses the
    access provider. Region and requester-pays settings alone do not suppress it.
    """
    if (
        opener_id == "xarray"
        and "backend_kwargs" in options
        and options["backend_kwargs"] is None
    ):
        return True
    holder = options.get("backend_kwargs") if opener_id == "xarray" else options
    if not isinstance(holder, dict) or "storage_options" not in holder:
        return False
    storage = holder["storage_options"]
    return (
        storage is None
        or isinstance(storage, dict)
        and bool(_CREDENTIALS & storage.keys())
    )


def _merge(
    base: dict[str, Any],
    layer: dict[str, Any],
    sources: dict[str, str],
    label: str,
    prefix: str = "",
) -> dict[str, Any]:
    """Merge one precedence layer into a copy and update leaf provenance.

    Recurse only through known option mappings; replace other values, including
    None. A storage layer choosing authentication replaces all inherited
    credential fields together, preventing mixed identities or stale tokens.
    ``sources`` is updated in place; input option mappings remain unchanged.
    """
    result = _copy_options(base)
    for key, value in layer.items():
        path = prefix + key
        for previous in list(sources):
            if previous == path or previous.startswith(path + "."):
                # Recursive mapping merges restore labels for surviving leaves.
                if not (
                    key in _MAPPINGS
                    and isinstance(value, dict)
                    and isinstance(result.get(key), dict)
                ):
                    sources.pop(previous)
        if (
            key == "storage_options"
            and isinstance(value, dict)
            and _CREDENTIALS & value.keys()
        ):
            inherited = result.get(key)
            if isinstance(inherited, dict):
                # Preserve non-credential settings such as region, but discard
                # the previous identity even if the new layer supplies only anon.
                for credential in _CREDENTIALS:
                    inherited.pop(credential, None)
        if key in _MAPPINGS and isinstance(value, dict):
            previous_value = result.get(key)
            result[key] = _merge(
                previous_value if isinstance(previous_value, dict) else {},
                value,
                sources,
                label,
                path + ".",
            )
        else:
            result[key] = _copy_options(value)
            sources[path] = label
    return result


def _warn() -> None:
    """Report ignored producer hints without exposing their potentially private values."""
    warnings.warn(
        "Ignored unsupported or invalid producer Asset reader hints",
        ClientWarning,
        stacklevel=3,
    )


def _valid(key: str, value: Any, opener_id: str) -> bool:
    """Check the value shape of one producer option; key allowlisting is separate."""
    if value is None:
        return True
    if opener_id == "xarray":
        if key == "chunks":
            # Exact type checks exclude booleans, which Python treats as integers.
            return (
                value == "auto"
                or type(value) is int
                and (value == -1 or value > 0)
                or isinstance(value, dict)
                and all(
                    isinstance(k, str) and type(v) is int and (v == -1 or v > 0)
                    for k, v in value.items()
                )
            )
        if key in {
            "decode_cf",
            "decode_times",
            "mask_and_scale",
            "cache",
            "consolidated",
        }:
            return type(value) is bool
        if key == "drop_variables":
            return (
                isinstance(value, str)
                or isinstance(value, list)
                and all(isinstance(v, str) for v in value)
            )
        if key == "backend_kwargs":
            return isinstance(value, dict) and all(
                k == "consolidated" and (v is None or type(v) is bool)
                for k, v in value.items()
            )
    if opener_id == "pandas":
        if key in {"sep", "delimiter", "encoding"}:
            return isinstance(value, str)
        if key == "header":
            return type(value) is int and value >= 0 or value == "infer"
        if key == "usecols":
            return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if opener_id == "geopandas" and key == "columns":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return False


def _validated(raw: Any, opener_id: str) -> dict[str, Any]:
    """Allowlist, copy, and normalize producer hints for one reader policy.

    Invalid or unsupported entries warn and are skipped instead of blocking
    asset reading. Storage hints have their own restricted validation policy.
    Engines and arbitrary backend arguments cannot be selected by producers.
    """
    if not isinstance(raw, dict):
        _warn()
        return {}
    result = {}
    for key, value in raw.items():
        allowed = (
            {
                "chunks",
                "decode_cf",
                "decode_times",
                "mask_and_scale",
                "cache",
                "drop_variables",
                "backend_kwargs",
                "consolidated",
            }
            if opener_id == "xarray"
            else {"sep", "delimiter", "encoding", "header", "usecols"}
            if opener_id == "pandas"
            else {"columns"}
            if opener_id == "geopandas"
            else set()
        )
        if key in allowed and _valid(key, value, opener_id):
            result[key] = deepcopy(value)
        elif key == "storage_options":
            result[key] = _validated_storage(value)
        else:
            _warn()
    return _normalize(result, opener_id)


def _validated_storage(raw: Any) -> dict[str, Any]:
    """Keep only producer-supplied region and requester-pays storage settings.

    Credentials, endpoints, and other arbitrary filesystem options must come
    from trusted client/caller options or the access provider, not STAC metadata.
    """
    if not isinstance(raw, dict):
        _warn()
        return {}
    result: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "requester_pays" and type(value) is bool:
            result[key] = value
        elif key == "client_kwargs" and isinstance(value, dict):
            region = value.get("region_name")
            if isinstance(region, str) and region:
                result[key] = {"region_name": region}
            if (
                set(value) - {"region_name"}
                or "region_name" in value
                and not (isinstance(region, str) and region)
            ):
                _warn()
        else:
            _warn()
    return result


def _producer_hints(
    asset: Any,
    opener_id: str,
    location: str,
    media_type: str | None,
    alternate: str | None = None,
) -> dict[str, Any]:
    """Read validated hints belonging to the selected primary or alternate href.

    Alternate fields replace primary fields rather than inheriting their hints.
    Standard extension hints require a matching declaration on the owner;
    application ``x-options`` use the same validation without that declaration.
    """
    fields = asset.extra_fields
    if alternate is not None:
        # Asset resolution already selected and validated this alternate.
        fields = fields["alternate"][alternate]
    hint_reader_id = opener_id
    if opener_id == "pandas" and not (
        (media_type or "").split(";", 1)[0] == "text/csv"
        or not media_type
        and urlsplit(location).path.endswith(".csv")
    ):
        # Separator/header hints describe CSV, not every pandas storage format.
        hint_reader_id = "storage-only"
    result = (
        _validated(fields["x-options"], hint_reader_id) if "x-options" in fields else {}
    )
    owner = asset.owner
    extensions = owner.stac_extensions if owner is not None else []
    xarray_fields = {
        key: value for key, value in fields.items() if key.startswith("xarray:")
    }
    if xarray_fields:
        # Do not apply extension fields unless both the extension and reader match.
        if _XARRAY in extensions and opener_id == "xarray":
            layer = (
                _validated(fields["xarray:open_kwargs"], opener_id)
                if "xarray:open_kwargs" in fields
                else {}
            )
            if "xarray:storage_options" in fields:
                layer = _merge(
                    layer,
                    _normalize(
                        {
                            "storage_options": _validated_storage(
                                fields["xarray:storage_options"]
                            )
                        },
                        opener_id,
                    ),
                    {},
                    "producer",
                )
            result = _merge(result, layer, {}, "producer")
            if set(xarray_fields) - {"xarray:open_kwargs", "xarray:storage_options"}:
                _warn()
        else:
            _warn()
    if (
        any(key.startswith("storage:") for key in fields)
        or _STORAGE_V1 in extensions
        or _STORAGE_V2 in extensions
    ):
        storage = _storage_hints(asset, extensions, location, fields)
        result = _merge(
            result,
            _normalize({"storage_options": storage}, opener_id),
            {},
            "producer",
        )
    return result


def _storage_hints(
    asset: Any, extensions: list[str], location: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Translate supported STAC storage v1/v2 metadata into scoped S3 options.

    V2 requires one unambiguous AWS scheme reference whose bucket matches the
    selected URL. V1 combines owner defaults with asset/alternate overrides.
    Prefer v2 when both versions are declared; never use S3 hints for other URLs.
    """
    owner = asset.owner
    properties = getattr(owner, "properties", getattr(owner, "extra_fields", {}))
    if not location.startswith("s3://"):
        return {}
    if _STORAGE_V2 in extensions:
        # Several references could describe different access paths; do not guess.
        refs = fields.get("storage:refs", [])
        schemes = properties.get("storage:schemes", {})
        if (
            not isinstance(refs, list)
            or len(refs) != 1
            or not isinstance(refs[0], str)
            or not isinstance(schemes, dict)
        ):
            _warn()
            return {}
        scheme = schemes.get(refs[0])
        # Restrict producer routing hints to this known AWS layout and bucket.
        if (
            not isinstance(scheme, dict)
            or scheme.get("type") != "aws-s3"
            or scheme.get("platform") != "https://{bucket}.s3.{region}.amazonaws.com"
            or scheme.get("bucket") != urlsplit(location).netloc
        ):
            _warn()
            return {}
        region, pays = scheme.get("region"), scheme.get("requester_pays")
    elif _STORAGE_V1 in extensions:
        # Asset-local values take precedence over the owner's storage defaults.
        merged = {**properties, **fields}
        if merged.get("storage:platform") != "AWS":
            _warn()
            return {}
        region, pays = (
            merged.get("storage:region"),
            merged.get("storage:requester_pays"),
        )
    else:
        _warn()
        return {}
    result: dict[str, Any] = {}
    if region is not None:
        if isinstance(region, str) and region:
            result["client_kwargs"] = {"region_name": region}
        else:
            _warn()
    if pays is not None:
        if type(pays) is bool:
            result["requester_pays"] = pays
        else:
            _warn()
    return result


def _non_secret(options: dict[str, Any]) -> dict[str, Any]:
    """Build diagnostic options without known secrets, private URLs, or runtime objects.

    Recursively copy dictionaries and simple values. These summaries are for
    provenance and callbacks; readers receive the original effective options.
    """
    result: dict[str, Any] = {}
    for key, value in options.items():
        if not isinstance(key, str):
            continue
        lowered = key.lower()
        # Cover credential aliases and nested containers such as HTTP headers.
        if lowered in _CREDENTIALS or any(
            part in lowered
            for part in (
                "secret",
                "token",
                "password",
                "credential",
                "session",
                "headers",
                "cookie",
                "access_key",
                "authorization",
                "api_key",
            )
        ):
            continue
        if isinstance(value, dict):
            result[key] = _non_secret(value)
        elif isinstance(value, (str, int, float, bool, list, type(None))):
            if isinstance(value, str) and _private_url(value):
                continue
            if isinstance(value, list):
                # Lists such as column names are allowed, runtime objects are not.
                if not all(
                    isinstance(v, (str, int, float, bool, type(None))) for v in value
                ):
                    continue
                if any(isinstance(v, str) and _private_url(v) for v in value):
                    continue
            result[key] = deepcopy(value)
    return result


def _private_url(value: str) -> bool:
    """Flag URLs with user information, query parameters, or invalid URL syntax."""
    if "://" not in value:
        return False
    try:
        parsed = urlsplit(value)
        return bool(parsed.query or parsed.username)
    except ValueError:
        # Malformed URLs cannot be safely classified for diagnostic disclosure.
        return True


def _has_path(options: dict[str, Any], path: str) -> bool:
    """Check a dotted provenance path against the retained diagnostic mappings."""
    value: Any = options
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return False
        value = value[key]
    return True
