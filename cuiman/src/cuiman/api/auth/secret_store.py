#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""OS-backed storage with a process-local fallback for authentication secrets."""

import hashlib
import json
import warnings
from functools import cache
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import keyring
from keyring.errors import PasswordDeleteError

from cuiman.warnings import SecretStoreFallbackWarning

KEYRING_SERVICE_NAME = "eozilla.cuiman"
"""Service name used for Cuiman entries in the operating-system keyring."""

# Windows stores strings as UTF-16 with a 2,560-byte limit per entry.
# JSON is ASCII-escaped, so each character occupies exactly two bytes there.
_CHUNK_SIZE = 1200
_CHUNK_FORMAT = "cuiman-chunks-v1"
_MAX_CHUNKS = 1024


class SecretStoreError(RuntimeError):
    """Raised when Cuiman cannot safely use the operating-system keyring."""


class _SecretStore(Protocol):
    def get_password(self, service: str, account: str, /) -> str | None: ...

    def set_password(self, service: str, account: str, value: str, /) -> None: ...

    def delete_password(self, service: str, account: str, /) -> None: ...


class _MemorySecretStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self._records.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        warnings.warn(
            "Operating-system secret store is unavailable. Credentials will be kept "
            "only in memory for this process and lost when it exits. Separate CLI "
            "commands cannot reuse them; configure a working keyring or supply "
            "credentials through environment variables or Python configuration.",
            SecretStoreFallbackWarning,
            stacklevel=2,
        )
        self._records[service, account] = value

    def delete_password(self, service: str, account: str) -> None:
        self._records.pop((service, account), None)


@cache
def _get_secret_store() -> _SecretStore:
    # Backend priority checks viability in this environment, including D-Bus
    # availability on Linux. Fail and null backends have non-positive priority.
    try:
        available = keyring.get_keyring().priority > 0
    except Exception:
        available = False
    if available:
        return keyring
    return _MemorySecretStore()


def get_keyring_account(config_path: Path | str, api_url: str) -> str:
    """Return a stable keyring account for a configuration file and API URL."""
    canonical_path = Path(config_path).expanduser().resolve(strict=False)
    identity = f"{canonical_path}\0{api_url}".encode()
    return hashlib.sha256(identity).hexdigest()


def load_auth_secrets(
    config_path: Path | str, api_url: str, auth_type: str
) -> dict[str, str]:
    """Load credentials from the keyring or process-local fallback."""
    account = get_keyring_account(config_path, api_url)
    stored_value = _get_password(KEYRING_SERVICE_NAME, account)
    if stored_value is None:
        return {}

    chunk_info = _chunk_info(stored_value)
    if chunk_info is not None:
        parts = []
        for service in _chunk_services(account, chunk_info):
            part = _get_password(service, account)
            if part is None:
                raise SecretStoreError(
                    "Stored credentials are incomplete. Please log in again."
                )
            parts.append(part)
        stored_value = "".join(parts)

    try:
        stored_data = json.loads(stored_value)
        stored_auth_type = stored_data["auth_type"]
        secrets = stored_data["secrets"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SecretStoreError("Stored credentials are invalid.") from exc
    if stored_auth_type != auth_type:
        return {}
    if not isinstance(secrets, dict) or not all(
        isinstance(name, str) and isinstance(value, str)
        for name, value in secrets.items()
    ):
        raise SecretStoreError("Stored credentials are invalid.")
    return secrets


def save_auth_secrets(
    config_path: Path | str,
    api_url: str,
    auth_type: str,
    secrets: dict[str, str],
) -> None:
    """Save credentials in the keyring or process-local fallback."""
    if not all(
        isinstance(name, str) and isinstance(value, str)
        for name, value in secrets.items()
    ):
        raise ValueError("Authentication secrets must have string names and values.")
    account = get_keyring_account(config_path, api_url)
    stored_value = json.dumps(
        {"auth_type": auth_type, "secrets": secrets}, sort_keys=True, ensure_ascii=True
    )
    previous = _chunk_info(_get_password(KEYRING_SERVICE_NAME, account))
    new_services: list[str] = []
    try:
        if len(stored_value) > _CHUNK_SIZE:
            parts = [
                stored_value[start : start + _CHUNK_SIZE]
                for start in range(0, len(stored_value), _CHUNK_SIZE)
            ]
            if len(parts) > _MAX_CHUNKS:
                raise SecretStoreError("Credentials exceed the storage limit.")
            generation = uuid4().hex
            for service, part in zip(
                _chunk_services(account, (generation, len(parts))), parts, strict=True
            ):
                new_services.append(service)
                _set_password(service, account, part)
            stored_value = json.dumps(
                {
                    "storage": _CHUNK_FORMAT,
                    "generation": generation,
                    "chunks": len(parts),
                }
            )
        # Publish only after every part was saved. A failed token update leaves
        # the old record and its parts intact.
        _set_password(KEYRING_SERVICE_NAME, account, stored_value)
    except SecretStoreError:
        for service in new_services:
            try:
                _delete_password(service, account)
            except SecretStoreError:
                pass  # Keep the original write error; never delete the old record.
        raise
    if previous is not None:
        for service in _chunk_services(account, previous):
            _delete_password(service, account)


def delete_auth_secrets(config_path: Path | str, api_url: str) -> None:
    """Remove credentials for a configuration file and API URL from the store."""
    account = get_keyring_account(config_path, api_url)
    chunk_info = _chunk_info(_get_password(KEYRING_SERVICE_NAME, account))
    if chunk_info is not None:
        for service in _chunk_services(account, chunk_info):
            _delete_password(service, account)
    _delete_password(KEYRING_SERVICE_NAME, account)


def _chunk_info(value: str | None) -> tuple[str, int] | None:
    try:
        data = json.loads(value) if value is not None else None
    except json.JSONDecodeError:
        return None  # load_auth_secrets validates ordinary/legacy records.
    if not isinstance(data, dict) or data.get("storage") != _CHUNK_FORMAT:
        return None
    generation, count = data.get("generation"), data.get("chunks")
    if (
        not isinstance(generation, str)
        or len(generation) != 32
        or any(char not in "0123456789abcdef" for char in generation)
        or type(count) is not int
        or not 1 <= count <= _MAX_CHUNKS
    ):
        raise SecretStoreError("Stored credential metadata is invalid.")
    return generation, count


def _chunk_services(account: str, info: tuple[str, int]) -> list[str]:
    generation, count = info
    return [
        f"{KEYRING_SERVICE_NAME}.{account}.{generation}.{index}"
        for index in range(count)
    ]


def _get_password(service: str, account: str) -> str | None:
    try:
        return _get_secret_store().get_password(service, account)
    except Exception as exc:
        # Some native backends (notably pywin32-ctypes) do not use KeyringError.
        raise SecretStoreError("Operating-system secret store is unavailable.") from exc


def _set_password(service: str, account: str, value: str) -> None:
    try:
        _get_secret_store().set_password(service, account, value)
    except Exception as exc:
        raise SecretStoreError("Operating-system secret store is unavailable.") from exc


def _delete_password(service: str, account: str) -> None:
    try:
        _get_secret_store().delete_password(service, account)
    except PasswordDeleteError:
        return
    except Exception as exc:
        raise SecretStoreError("Operating-system secret store is unavailable.") from exc
