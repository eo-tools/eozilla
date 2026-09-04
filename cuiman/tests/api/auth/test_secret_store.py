#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from keyring.errors import KeyringError, PasswordDeleteError

from cuiman.api.auth.secret_store import (
    KEYRING_SERVICE_NAME,
    SecretStoreError,
    delete_auth_secrets,
    get_keyring_account,
    load_auth_secrets,
    save_auth_secrets,
)


def test_keyring_account_is_scoped_by_config_path_and_api_url(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    account = get_keyring_account(config_path, "https://api.example.test/")

    assert account == get_keyring_account(config_path, "https://api.example.test/")
    assert account != get_keyring_account(config_path, "https://other.example.test/")
    assert account != get_keyring_account(
        tmp_path / "other.yaml", "https://api.example.test/"
    )


@patch("cuiman.api.auth.secret_store.keyring.get_password")
def test_load_auth_secrets_reads_matching_record(mock_get_password, tmp_path: Path):
    mock_get_password.return_value = json.dumps(
        {
            "auth_type": "login",
            "secrets": {"username": "u", "password": "p", "access_token": "t"},
        }
    )

    secrets = load_auth_secrets(
        tmp_path / "config", "https://api.example.test/", "login"
    )

    assert secrets == {"username": "u", "password": "p", "access_token": "t"}
    mock_get_password.assert_called_once_with(
        KEYRING_SERVICE_NAME,
        get_keyring_account(tmp_path / "config", "https://api.example.test/"),
    )


@patch("cuiman.api.auth.secret_store.keyring.get_password")
def test_load_auth_secrets_ignores_record_for_another_auth_type(
    mock_get_password, tmp_path: Path
):
    mock_get_password.return_value = json.dumps(
        {"auth_type": "token", "secrets": {"access_token": "t"}}
    )

    assert (
        load_auth_secrets(tmp_path / "config", "https://api.example.test/", "login")
        == {}
    )


@patch("cuiman.api.auth.secret_store.keyring.get_password")
def test_load_auth_secrets_rejects_invalid_record(mock_get_password, tmp_path: Path):
    mock_get_password.return_value = "not-json"

    with pytest.raises(SecretStoreError, match="Stored Cuiman credentials are invalid"):
        load_auth_secrets(tmp_path / "config", "https://api.example.test/", "login")


@patch("cuiman.api.auth.secret_store.keyring.get_password")
def test_load_auth_secrets_rejects_non_string_secret_value(
    mock_get_password, tmp_path: Path
):
    mock_get_password.return_value = json.dumps(
        {"auth_type": "token", "secrets": {"access_token": 1}}
    )

    with pytest.raises(SecretStoreError, match="Stored Cuiman credentials are invalid"):
        load_auth_secrets(tmp_path / "config", "https://api.example.test/", "token")


@patch("cuiman.api.auth.secret_store.keyring.get_password")
def test_load_auth_secrets_reports_unavailable_keyring(
    mock_get_password, tmp_path: Path
):
    mock_get_password.side_effect = KeyringError("unavailable")

    with pytest.raises(SecretStoreError, match="secret store is unavailable"):
        load_auth_secrets(tmp_path / "config", "https://api.example.test/", "login")


@patch("cuiman.api.auth.secret_store.keyring.set_password")
def test_save_auth_secrets_writes_typed_record(mock_set_password, tmp_path: Path):
    config_path = tmp_path / "config"

    save_auth_secrets(
        config_path,
        "https://api.example.test/",
        "login",
        {"username": "u", "password": "p"},
    )

    service, account, stored_value = mock_set_password.call_args.args
    assert service == KEYRING_SERVICE_NAME
    assert account == get_keyring_account(config_path, "https://api.example.test/")
    assert json.loads(stored_value) == {
        "auth_type": "login",
        "secrets": {"username": "u", "password": "p"},
    }


def test_save_auth_secrets_rejects_non_string_secret_value(tmp_path: Path):
    with pytest.raises(ValueError, match="Authentication secrets must have string"):
        save_auth_secrets(
            tmp_path / "config",
            "https://api.example.test/",
            "token",
            {"access_token": 1},  # type: ignore[dict-item]
        )


@patch("cuiman.api.auth.secret_store.keyring.set_password")
def test_save_auth_secrets_reports_unavailable_keyring(
    mock_set_password, tmp_path: Path
):
    mock_set_password.side_effect = KeyringError("unavailable")

    with pytest.raises(SecretStoreError, match="secret store is unavailable"):
        save_auth_secrets(
            tmp_path / "config",
            "https://api.example.test/",
            "login",
            {"username": "u", "password": "p"},
        )


@patch("cuiman.api.auth.secret_store.keyring.delete_password")
def test_delete_auth_secrets_ignores_missing_record(
    mock_delete_password, tmp_path: Path
):
    mock_delete_password.side_effect = PasswordDeleteError("missing")

    delete_auth_secrets(tmp_path / "config", "https://api.example.test/")


@patch("cuiman.api.auth.secret_store.keyring.delete_password")
def test_delete_auth_secrets_reports_unavailable_keyring(
    mock_delete_password, tmp_path: Path
):
    mock_delete_password.side_effect = KeyringError("unavailable")

    with pytest.raises(SecretStoreError, match="secret store is unavailable"):
        delete_auth_secrets(tmp_path / "config", "https://api.example.test/")
