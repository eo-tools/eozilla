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
_MAPPINGS = {
    "chunks",
    "backend_kwargs",
    "storage_options",
    "client_kwargs",
    "config_kwargs",
}
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
    ctx: JobResultOpenContext, asset_reader_id: str
) -> JobResultOpenContext:
    """Resolve independent reader options and acquire access for one accepted Asset."""
    asset = as_stac_asset(ctx.value)
    assert asset is not None
    defaults: dict[str, Any] = {}
    if asset_reader_id == "xarray" and (
        (ctx.output_media_type or "").split(";", 1)[0]
        in {"application/x-zarr", "application/vnd+zarr"}
        or not ctx.output_media_type
        and urlsplit(ctx.location or "").path.rstrip("/").endswith(".zarr")
    ):
        defaults = {"engine": "zarr"}
    callback_ctx = replace(ctx, options=_copy_options(ctx.options))
    factory = type(ctx.config).asset_reader_options
    overrides = factory(callback_ctx, asset_reader_id) if factory else {}
    if not isinstance(overrides, dict):
        raise JobResultOpenError("Asset reader overrides must be a mapping")
    caller = _normalize(ctx.options, asset_reader_id)
    client = _normalize(overrides, asset_reader_id)
    effective: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for label, layer in (
        ("reader-default", defaults),
        (
            "producer",
            _producer_hints(
                asset, asset_reader_id, ctx.location or "", ctx.output_media_type
            ),
        ),
        ("client", client),
        ("caller", caller),
    ):
        effective = _merge(effective, layer, sources, label)
    ctx.resolved_options = _non_secret(effective)
    ctx.option_sources = {
        path: source
        for path, source in sources.items()
        if _has_path(ctx.resolved_options, path)
    }
    storage = _storage(effective, asset_reader_id)
    # Explicit clearing and trusted credentials control access without invoking
    # a provider. A replacement always discards old tokens as well as old keys.
    controls = any(
        _controls_access(layer, asset_reader_id) for layer in (client, caller)
    )
    provider = type(ctx.config).asset_access_provider
    if (ctx.location or "").startswith("s3://") and provider and not controls:
        access_ctx = replace(ctx, options=deepcopy(ctx.resolved_options))
        access = provider(access_ctx, asset_reader_id)
        if isawaitable(access):
            access = await access
        if access is not None:
            if not isinstance(access, dict):
                raise JobResultOpenError(
                    "Asset access provider must return a mapping or None"
                )
            provided = _normalize({"storage_options": access}, asset_reader_id)
            access_sources: dict[str, str] = {}
            _merge({}, provided, access_sources, "access-provider")
            # Trusted reader overrides still take precedence over provider defaults.
            effective = _merge(provided, effective, {}, "reader")
            sources = {**access_sources, **sources}
            storage = _storage(effective, asset_reader_id)
    if storage is not None and not isinstance(storage, dict):
        raise JobResultOpenError("Asset storage options must be a mapping or None")
    ctx.resolved_options = _non_secret(effective)
    ctx.option_sources = {
        path: source
        for path, source in sources.items()
        if _has_path(ctx.resolved_options, path)
    }
    return replace(ctx, options=effective)


def _normalize(options: dict[str, Any], asset_reader_id: str) -> dict[str, Any]:
    result = _copy_options(options)
    if asset_reader_id == "xarray":
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


def _storage(options: dict[str, Any], asset_reader_id: str) -> Any:
    holder = options.get("backend_kwargs") if asset_reader_id == "xarray" else options
    return holder.get("storage_options") if isinstance(holder, dict) else None


def _controls_access(options: dict[str, Any], asset_reader_id: str) -> bool:
    if (
        asset_reader_id == "xarray"
        and "backend_kwargs" in options
        and options["backend_kwargs"] is None
    ):
        return True
    holder = options.get("backend_kwargs") if asset_reader_id == "xarray" else options
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
    warnings.warn(
        "Ignored unsupported or invalid producer Asset reader hints",
        ClientWarning,
        stacklevel=3,
    )


def _valid(key: str, value: Any, asset_reader_id: str) -> bool:
    if value is None:
        return True
    if asset_reader_id == "xarray":
        if key == "chunks":
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
    if asset_reader_id == "pandas":
        if key in {"sep", "delimiter", "encoding"}:
            return isinstance(value, str)
        if key == "header":
            return type(value) is int and value >= 0 or value == "infer"
        if key == "usecols":
            return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if asset_reader_id == "geopandas" and key == "columns":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return False


def _validated(raw: Any, asset_reader_id: str) -> dict[str, Any]:
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
            if asset_reader_id == "xarray"
            else {"sep", "delimiter", "encoding", "header", "usecols"}
            if asset_reader_id == "pandas"
            else {"columns"}
            if asset_reader_id == "geopandas"
            else set()
        )
        if key in allowed and _valid(key, value, asset_reader_id):
            result[key] = deepcopy(value)
        elif key == "storage_options":
            result[key] = _validated_storage(value)
        else:
            _warn()
    return _normalize(result, asset_reader_id)


def _validated_storage(raw: Any) -> dict[str, Any]:
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
    asset: Any, asset_reader_id: str, location: str, media_type: str | None
) -> dict[str, Any]:
    fields = asset.extra_fields
    hint_reader_id = asset_reader_id
    if asset_reader_id == "pandas" and not (
        (media_type or "").split(";", 1)[0] == "text/csv"
        or not media_type
        and urlsplit(location).path.endswith(".csv")
    ):
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
        if _XARRAY in extensions and asset_reader_id == "xarray":
            layer = (
                _validated(fields["xarray:open_kwargs"], asset_reader_id)
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
                        asset_reader_id,
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
        storage = _storage_hints(asset, extensions, location)
        result = _merge(
            result,
            _normalize({"storage_options": storage}, asset_reader_id),
            {},
            "producer",
        )
    return result


def _storage_hints(asset: Any, extensions: list[str], location: str) -> dict[str, Any]:
    owner = asset.owner
    properties = getattr(owner, "properties", getattr(owner, "extra_fields", {}))
    fields = asset.extra_fields
    if not location.startswith("s3://"):
        return {}
    if _STORAGE_V2 in extensions:
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
    result: dict[str, Any] = {}
    for key, value in options.items():
        if not isinstance(key, str):
            continue
        lowered = key.lower()
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
    if "://" not in value:
        return False
    try:
        parsed = urlsplit(value)
        return bool(parsed.query or parsed.username)
    except ValueError:
        return True


def _has_path(options: dict[str, Any], path: str) -> bool:
    value: Any = options
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return False
        value = value[key]
    return True
