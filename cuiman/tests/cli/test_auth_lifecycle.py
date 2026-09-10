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


@pytest.mark.parametrize(
    "auth,secret",
    [
        ({"auth_type": "basic"}, {"username": "user", "password": "password"}),
        ({"auth_type": "token"}, {"access_token": "token"}),
        ({"auth_type": "api-key"}, {"api_key": "key"}),
        (
            {"auth_type": "login", "login_url": "https://identity.test/login"},
            {"access_token": "token"},
        ),
        (
            {
                "auth_type": "oauth2",
                "token_url": "https://identity.test/token",
                "client_id": "client",
            },
            {"oauth_token": '{"access_token":"saved"}'},
        ),
        (
            {
                "auth_type": "oidc",
                "issuer_url": "https://identity.test/realm",
                "client_id": "client",
            },
            {"oauth_token": '{"access_token":"saved"}'},
        ),
    ],
)
def test_saved_login_reuses_credentials_without_interaction(
    auth, secret, auth_provider, monkeypatch
):
    ClientConfig(api_url="https://processing.test", auth=auth).write()
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", lambda *args: secret)
    monkeypatch.setattr(
        "typer.prompt", Mock(side_effect=AssertionError("unexpected prompt"))
    )
    monkeypatch.setattr(
        "cuiman.api.client_mixin.authorize",
        Mock(side_effect=AssertionError("unexpected browser")),
    )
    saved = Mock()
    monkeypatch.setattr("cuiman.api.auth.oauth2_client.save_auth_secrets", saved)
    login_client_with_prompt()
    saved.assert_called_once()
    assert auth_provider.grants == []


def test_cli_no_input_can_force_fresh_grant_using_supplied_credentials(
    auth_provider, monkeypatch
):
    from typer.testing import CliRunner
    from cuiman.cli.cli import cli

    ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.test/token",
            "client_id": "client",
        },
    ).write()
    monkeypatch.setenv("EOZILLA_AUTH__USERNAME", "user")
    monkeypatch.setenv("EOZILLA_AUTH__PASSWORD", "password")
    monkeypatch.setattr(
        "typer.prompt", Mock(side_effect=AssertionError("unexpected prompt"))
    )
    monkeypatch.setattr("cuiman.api.auth.oauth2_client.save_auth_secrets", Mock())
    result = CliRunner().invoke(cli, ["login", "--force", "--no-input"])
    assert result.exit_code == 0, result.output
    assert auth_provider.grants[-1]["username"] == ["user"]


def test_cli_no_input_reports_missing_credentials_without_prompting(monkeypatch):
    from typer.testing import CliRunner
    from cuiman.cli.cli import cli

    ClientConfig(api_url="https://processing.test", auth={"auth_type": "token"}).write()
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", lambda *args: {})
    monkeypatch.setattr(
        "typer.prompt", Mock(side_effect=AssertionError("unexpected prompt"))
    )
    result = CliRunner().invoke(cli, ["login", "--no-input"])
    assert result.exit_code == 1
    assert "cuiman login" in result.output
    assert "Login completed" not in result.output


@pytest.mark.parametrize("command", ["login", "list-processes"])
def test_cli_auth_error_does_not_echo_provider_response(
    command, auth_provider, monkeypatch
):
    from typer.testing import CliRunner
    from cuiman.cli.cli import cli

    ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "oauth2",
            "token_url": "https://identity.test/token",
            "client_id": "client",
        },
    ).write()
    monkeypatch.setattr(
        "cuiman.api.config.load_auth_secrets",
        lambda *args: {
            "oauth_token": '{"access_token":"old","refresh_token":"old-refresh","expires_at":1}'
        },
    )
    auth_provider.replies.append(
        (400, {"error": "invalid_grant", "error_description": "DO-NOT-ECHO"})
    )
    result = CliRunner().invoke(cli, [command])
    assert result.exit_code == 1
    assert "login --force" in result.output
    assert "DO-NOT-ECHO" not in result.output
    assert "Login completed" not in result.output


def test_cli_logout_reports_revocation_failure_and_still_removes_local_credentials(
    auth_provider, monkeypatch
):
    from typer.testing import CliRunner
    from cuiman.cli.cli import cli

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
        lambda *args: {"oauth_token": '{"access_token":"saved"}'},
    )
    deleted = Mock()
    monkeypatch.setattr("cuiman.api.client_mixin_base.delete_auth_secrets", deleted)
    auth_provider.revoke_status = 503
    result = CliRunner().invoke(cli, ["logout"])
    assert result.exit_code == 1
    assert "Authentication failed" in result.output
    assert "https://identity.test" not in result.output
    deleted.assert_called_once()


def test_cli_configure_exposes_api_key_header_and_rejects_irrelevant_options(tmp_path):
    from typer.testing import CliRunner
    from cuiman.cli.cli import cli

    path = tmp_path / "named"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "configure",
            "--config",
            str(path),
            "--api-url",
            "https://processing.test",
            "--auth-type",
            "api-key",
            "--api-key-header",
            "X-Custom",
        ],
    )
    assert result.exit_code == 0, result.output
    assert ClientConfig.from_file(path).auth.api_key_header == "X-Custom"
    before = path.read_text()
    result = runner.invoke(
        cli,
        [
            "configure",
            "--config",
            str(path),
            "--api-url",
            "https://processing.test",
            "--auth-type",
            "none",
            "--client-id",
            "irrelevant",
        ],
    )
    assert result.exit_code == 1
    assert "do not apply" in result.output
    assert path.read_text() == before
