#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""OS-backed storage for Cuiman authentication secrets."""

import hashlib
import json
from pathlib import Path

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

KEYRING_SERVICE_NAME = "eozilla.cuiman"
"""Service name used for Cuiman entries in the operating-system keyring."""


class SecretStoreError(RuntimeError):
    """Raised when Cuiman cannot safely use the operating-system keyring."""


def get_keyring_account(config_path: Path | str, api_url: str) -> str:
    """Return a stable keyring account for a configuration file and API URL."""
    canonical_path = Path(config_path).expanduser().resolve(strict=False)
    identity = f"{canonical_path}\0{api_url}".encode()
    return hashlib.sha256(identity).hexdigest()


def load_auth_secrets(
    config_path: Path | str, api_url: str, auth_type: str
) -> dict[str, str]:
    """Load credentials for an authentication configuration from the keyring."""
    account = get_keyring_account(config_path, api_url)
    try:
        stored_value = keyring.get_password(KEYRING_SERVICE_NAME, account)
    except KeyringError as exc:
        raise SecretStoreError("Operating-system secret store is unavailable.") from exc
    if stored_value is None:
        return {}

    try:
        stored_data = json.loads(stored_value)
        stored_auth_type = stored_data["auth_type"]
        secrets = stored_data["secrets"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SecretStoreError("Stored Cuiman credentials are invalid.") from exc
    if stored_auth_type != auth_type:
        return {}
    if not isinstance(secrets, dict) or not all(
        isinstance(name, str) and isinstance(value, str)
        for name, value in secrets.items()
    ):
        raise SecretStoreError("Stored Cuiman credentials are invalid.")
    return secrets


def save_auth_secrets(
    config_path: Path | str,
    api_url: str,
    auth_type: str,
    secrets: dict[str, str],
) -> None:
    """Persist credentials for an authentication configuration in the keyring."""
    if not all(
        isinstance(name, str) and isinstance(value, str)
        for name, value in secrets.items()
    ):
        raise ValueError("Authentication secrets must have string names and values.")
    account = get_keyring_account(config_path, api_url)
    stored_value = json.dumps(
        {"auth_type": auth_type, "secrets": secrets}, sort_keys=True
    )
    try:
        keyring.set_password(KEYRING_SERVICE_NAME, account, stored_value)
    except KeyringError as exc:
        raise SecretStoreError("Operating-system secret store is unavailable.") from exc


def delete_auth_secrets(config_path: Path | str, api_url: str) -> None:
    """Remove credentials for a configuration file and API URL from the keyring."""
    account = get_keyring_account(config_path, api_url)
    try:
        keyring.delete_password(KEYRING_SERVICE_NAME, account)
    except PasswordDeleteError:
        return
    except KeyringError as exc:
        raise SecretStoreError("Operating-system secret store is unavailable.") from exc
