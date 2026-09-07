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


class NativeCredentialError(Exception):
    """Native errors need not inherit KeyringError or OSError."""


@pytest.fixture(autouse=True)
def credential_store(monkeypatch):
    records = {}

    def write(service, account, value):
        if len(value.encode("utf-16-le")) > 2560:
            raise NativeCredentialError(1783, "CredWrite", "The stub received bad data")
        records[service, account] = value

    def delete(service, account):
        if (service, account) not in records:
            raise PasswordDeleteError("missing")
        del records[service, account]

    monkeypatch.setattr(
        "cuiman.api.auth.secret_store.keyring.get_password",
        lambda service, account: records.get((service, account)),
    )
    monkeypatch.setattr("cuiman.api.auth.secret_store.keyring.set_password", write)
    monkeypatch.setattr("cuiman.api.auth.secret_store.keyring.delete_password", delete)
    return records


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


@patch("cuiman.api.auth.secret_store.keyring.get_password", return_value=None)
def test_load_auth_secrets_handles_missing_record(_mock_get_password, tmp_path: Path):
    assert (
        load_auth_secrets(tmp_path / "config", "https://api.example.test/", "login")
        == {}
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


@pytest.mark.parametrize("value", ["x" * 6000, "\U0001f511" * 1400])
def test_large_tokens_roundtrip_and_logout(tmp_path, credential_store, value):
    path, url = tmp_path / "config", "https://api.example.test/"
    secrets = {"access_token": value, "refresh_token": "refresh" * 700}
    save_auth_secrets(path, url, "oidc", secrets)
    assert len(credential_store) > 2
    assert all(
        len(blob.encode("utf-16-le")) <= 2560 for blob in credential_store.values()
    )
    assert load_auth_secrets(path, url, "oidc") == secrets
    assert load_auth_secrets(path, url, "oauth2") == {}
    delete_auth_secrets(path, url)
    assert credential_store == {}
    delete_auth_secrets(path, url)


def test_rotated_tokens_remove_previous_parts(tmp_path, credential_store):
    path, url = tmp_path / "config", "https://api.example.test/"
    save_auth_secrets(path, url, "oidc", {"access_token": "a" * 5000})
    old_parts = {key for key in credential_store if key[0] != KEYRING_SERVICE_NAME}
    save_auth_secrets(path, url, "oidc", {"access_token": "b" * 5000})
    assert not old_parts.intersection(credential_store)
    assert load_auth_secrets(path, url, "oidc") == {"access_token": "b" * 5000}
    save_auth_secrets(path, url, "oidc", {"access_token": "small"})
    assert len(credential_store) == 1
    assert load_auth_secrets(path, url, "oidc") == {"access_token": "small"}


@pytest.mark.parametrize("fail_on", ["part", "manifest"])
def test_failed_token_update_keeps_previous_session(
    tmp_path, credential_store, monkeypatch, fail_on
):
    path, url = tmp_path / "config", "https://api.example.test/"
    save_auth_secrets(path, url, "oidc", {"access_token": "old" * 2000})
    previous = dict(credential_store)

    def failing_write(service, account, value):
        if (fail_on == "part" and service.endswith(".1")) or (
            fail_on == "manifest" and service == KEYRING_SERVICE_NAME
        ):
            raise NativeCredentialError(1783, "CredWrite", "failure")
        credential_store[service, account] = value

    monkeypatch.setattr(
        "cuiman.api.auth.secret_store.keyring.set_password", failing_write
    )
    with pytest.raises(SecretStoreError, match="secret store is unavailable"):
        save_auth_secrets(path, url, "oidc", {"access_token": "new" * 2000})
    assert credential_store == previous
    assert load_auth_secrets(path, url, "oidc") == {"access_token": "old" * 2000}


def test_chunked_credentials_are_scoped_to_the_profile(tmp_path, credential_store):
    first, second = tmp_path / "first", tmp_path / "second"
    url = "https://api.example.test/"
    save_auth_secrets(first, url, "oidc", {"access_token": "a" * 4000})
    save_auth_secrets(second, url, "oidc", {"access_token": "b" * 4000})
    delete_auth_secrets(first, url)
    assert load_auth_secrets(first, url, "oidc") == {}
    assert load_auth_secrets(second, url, "oidc") == {"access_token": "b" * 4000}


def test_missing_part_raises_controlled_error_and_logout_cleans_up(
    tmp_path, credential_store
):
    path, url = tmp_path / "config", "https://api.example.test/"
    save_auth_secrets(path, url, "oidc", {"access_token": "a" * 4000})
    key = next(key for key in credential_store if key[0] != KEYRING_SERVICE_NAME)
    del credential_store[key]
    with pytest.raises(SecretStoreError, match="incomplete"):
        load_auth_secrets(path, url, "oidc")
    delete_auth_secrets(path, url)
    assert credential_store == {}


@pytest.mark.parametrize(
    "generation,count",
    [(None, 2), ("a" * 32, -1), ("a" * 32, True), ("z" * 32, 2), ("a" * 32, 1000000)],
)
def test_invalid_manifest_is_rejected(tmp_path, credential_store, generation, count):
    path, url = tmp_path / "config", "https://api.example.test/"
    credential_store[KEYRING_SERVICE_NAME, get_keyring_account(path, url)] = json.dumps(
        {"storage": "cuiman-chunks-v1", "generation": generation, "chunks": count}
    )
    with pytest.raises(SecretStoreError, match="metadata is invalid"):
        load_auth_secrets(path, url, "oidc")


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_native_backend_errors_are_reported_safely(tmp_path, monkeypatch, operation):
    def fail(*args):
        raise NativeCredentialError(1783, "CredWrite", "sensitive backend detail")

    monkeypatch.setattr(
        f"cuiman.api.auth.secret_store.keyring.{operation}_password", fail
    )
    with pytest.raises(SecretStoreError) as caught:
        if operation == "get":
            load_auth_secrets(tmp_path / "config", "https://api.example.test/", "oidc")
        elif operation == "set":
            save_auth_secrets(
                tmp_path / "config", "https://api.example.test/", "oidc", {}
            )
        else:
            delete_auth_secrets(tmp_path / "config", "https://api.example.test/")
    assert "sensitive" not in str(caught.value)


def test_unreasonably_large_record_is_rejected_before_writes(
    tmp_path, credential_store
):
    with pytest.raises(SecretStoreError, match="storage limit"):
        save_auth_secrets(
            tmp_path / "config",
            "https://api.example.test/",
            "oidc",
            {"access_token": "a" * 1_300_000},
        )
    assert credential_store == {}
