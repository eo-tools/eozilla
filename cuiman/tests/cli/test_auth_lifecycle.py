"""CLI sign-in uses the same live client and explicit durable-save operation."""

import json
from unittest.mock import Mock

import pytest

from cuiman import ClientConfig
from cuiman.api.auth.secret_store import SecretStoreError
from cuiman.cli.config import login_client_with_prompt, logout_client


@pytest.mark.parametrize(
    "auth,answers",
    [
        ({"auth_type": "basic"}, ["user", "pass"]),
        ({"auth_type": "token"}, ["token"]),
        ({"auth_type": "api-key"}, ["key"]),
        (
            {"auth_type": "login", "login_url": "https://identity.test/login"},
            ["user", "pass"],
        ),
        (
            {
                "auth_type": "oauth2",
                "token_url": "https://identity.test/token",
                "client_id": "client",
            },
            ["user", "pass"],
        ),
        (
            {
                "auth_type": "oauth2",
                "token_url": "https://identity.test/token",
                "client_id": "client",
                "grant_type": "client_credentials",
            },
            ["secret"],
        ),
        (
            {
                "auth_type": "oidc",
                "issuer_url": "https://identity.test/realm",
                "client_id": "client",
            },
            [],
        ),
    ],
)
def test_cli_login_saves_once_through_shared_client(
    auth, answers, auth_provider, monkeypatch, tmp_path
):
    path = tmp_path / "config"
    ClientConfig(api_url="https://processing.test", auth=auth).write(path)
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", lambda *a: {})
    monkeypatch.setattr("typer.prompt", Mock(side_effect=answers))
    saved = Mock()
    monkeypatch.setattr("cuiman.api.auth.oauth2_client.save_auth_secrets", saved)
    login_client_with_prompt(path, no_browser=True)
    saved.assert_called_once()
    assert saved.call_args.args[:3] == (
        path,
        "https://processing.test/",
        auth["auth_type"],
    )
    secrets = saved.call_args.args[3]
    if auth["auth_type"] in ("oidc", "oauth2"):
        assert json.loads(secrets["oauth_token"])["access_token"] == "access-1"
        assert "access_token" not in secrets


def test_cli_explicit_save_failure_is_not_reported_as_success(
    auth_provider, monkeypatch, capsys
):
    ClientConfig(api_url="https://processing.test", auth={"auth_type": "token"}).write()
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", lambda *a: {})
    monkeypatch.setattr("typer.prompt", lambda *a, **k: "token")
    monkeypatch.setattr(
        "cuiman.api.auth.oauth2_client.save_auth_secrets",
        Mock(side_effect=SecretStoreError("unavailable")),
    )
    with pytest.raises(SecretStoreError):
        login_client_with_prompt()
    assert "Login completed" not in capsys.readouterr().out


def test_cli_environment_credentials_can_be_saved_explicitly(
    auth_provider, monkeypatch
):
    ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.test/token",
            "client_id": "client",
            "grant_type": "client_credentials",
        },
    ).write()
    monkeypatch.setenv("EOZILLA_AUTH__CLIENT_SECRET", "secret")
    saved = Mock()
    monkeypatch.setattr("cuiman.api.auth.oauth2_client.save_auth_secrets", saved)
    login_client_with_prompt()
    saved.assert_called_once()


def test_cli_none_logout_and_missing_config(monkeypatch, capsys, tmp_path):
    with pytest.raises(ValueError, match="not yet been configured"):
        login_client_with_prompt()
    with pytest.raises(ValueError, match="not found"):
        login_client_with_prompt(tmp_path / "missing")
    ClientConfig(api_url="https://processing.test").write()
    login_client_with_prompt()
    assert "does not require login" in capsys.readouterr().out
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    logout_client()
    deleted.assert_called_once()


def test_cli_logout_can_remove_an_unreadable_credential_record(monkeypatch):
    ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "oidc",
            "issuer_url": "https://identity.test/realm",
            "client_id": "client",
        },
    ).write()
    monkeypatch.setattr(
        "cuiman.api.config.load_auth_secrets",
        Mock(side_effect=SecretStoreError("unreadable")),
    )
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    logout_client()
    deleted.assert_called_once()
