"""Configure and load profiles through the same public interface as the CLI."""

import os
from pathlib import Path
from typing import ClassVar
from unittest.mock import Mock

import pytest
import yaml
from typer.testing import CliRunner

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import AuthConfig, TokenAuthConfig
from cuiman.cli.cli import new_cli
from cuiman.cli.config import configure_client_with_prompt, get_config


@pytest.fixture(autouse=True)
def clear_environment(monkeypatch):
    for name in os.environ:
        if name.startswith("EOZILLA_"):
            monkeypatch.delenv(name)


def test_missing_profiles_have_actionable_errors(tmp_path):
    with pytest.raises(ValueError, match="not yet been configured"):
        get_config(None)
    with pytest.raises(ValueError, match="not found or empty"):
        get_config(tmp_path / "missing")


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("required", [False, True])
def test_python_clients_do_not_require_a_config_file(client_type, required):
    class ApplicationConfig(ClientConfig):
        require_config_file = required

    config = ApplicationConfig.create()
    assert not config._has_profile
    assert not client_type(config_type=ApplicationConfig).config._has_profile


@pytest.mark.parametrize("contents", [None, ""])
def test_optional_default_profile_uses_validated_sources(
    contents, monkeypatch, tmp_path
):
    class ApplicationConfig(ClientConfig):
        require_config_file = False
        default_path = tmp_path / "optional-config"
        api_url: str | None = "https://default.test/"
        project: str

    if contents is not None:
        ApplicationConfig.default_path.write_text(contents)
    with pytest.raises(ValueError, match="project"):
        get_config(None, config_type=ApplicationConfig)

    monkeypatch.setenv("EOZILLA_PROJECT", "environment-project")
    monkeypatch.setenv("EOZILLA_API_URL", "https://environment.test/")
    config = get_config(None, config_type=ApplicationConfig)
    assert config.project == "environment-project"
    assert config.api_url == "https://environment.test/"
    assert not config._has_profile
    assert "require_config_file" not in config.to_file_dict()
    assert "require_config_file" not in ApplicationConfig.model_fields
    assert ClientConfig.require_config_file is True


@pytest.mark.parametrize("contents", [None, ""])
def test_optional_default_does_not_allow_missing_explicit_profiles(contents, tmp_path):
    class ApplicationConfig(ClientConfig):
        require_config_file = False

    path = tmp_path / "selected"
    if contents is not None:
        path.write_text(contents)
    with pytest.raises(ValueError, match="not found or empty"):
        get_config(path, config_type=ApplicationConfig)


def test_optional_profile_still_loads_and_validates_existing_files(tmp_path):
    class ApplicationConfig(ClientConfig):
        require_config_file = False
        default_path = tmp_path / "optional-config"
        api_url: str | None = "https://default.test/"

    ApplicationConfig.default_path.write_text("api_url: https://saved.test/\n")
    config = get_config(None, config_type=ApplicationConfig)
    assert config.api_url == "https://saved.test/"
    assert config._has_profile

    ApplicationConfig.default_path.write_text("invalid: [")
    with pytest.raises(ValueError, match="Deprecated or illegal"):
        get_config(None, config_type=ApplicationConfig)


def test_optional_profile_still_requires_login_and_can_skip_keyring(monkeypatch):
    class ApplicationConfig(ClientConfig):
        require_config_file = False
        auth: AuthConfig = TokenAuthConfig()

    load = Mock(return_value={})
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", load)
    with pytest.raises(ValueError, match="'default-client login'"):
        get_config(None, config_type=ApplicationConfig, cli_name="default-client")
    load.assert_called_once()

    load.reset_mock()
    config = get_config(
        None,
        config_type=ApplicationConfig,
        require_credentials=False,
        resolve_secrets=False,
    )
    assert config.auth.access_token is None
    load.assert_not_called()


@pytest.mark.parametrize(
    "auth",
    [
        {"auth_type": "token"},
        {
            "auth_type": "oauth2",
            "token_url": "https://identity.test/token",
            "client_id": "client",
            "grant_type": "client_credentials",
        },
    ],
)
def test_load_allows_missing_credentials_only_for_login(auth, monkeypatch):
    ClientConfig(api_url="https://processing.test", auth=auth).write()
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", lambda *args: {})
    with pytest.raises(ValueError, match="the 'login' command"):
        get_config(None)
    assert (
        get_config(None, require_credentials=False).auth.auth_type == auth["auth_type"]
    )


def test_load_uses_keyring_and_retains_profile(monkeypatch, tmp_path):
    path = tmp_path / "named"
    ClientConfig(api_url="https://processing.test", auth=TokenAuthConfig()).write(path)
    monkeypatch.setattr(
        "cuiman.api.config.load_auth_secrets", lambda *args: {"access_token": "stored"}
    )
    assert get_config(path).auth.access_token == "stored"
    assert get_config(path)._source_path == path


@pytest.mark.parametrize(
    "answers, expected",
    [
        (["none"], {"auth_type": "none"}),
        (["basic"], {"auth_type": "basic"}),
        (["token", ""], {"auth_type": "token"}),
        (
            ["token", "X-Custom"],
            {"auth_type": "token", "access_token_header": "X-Custom"},
        ),
        (
            ["login", "https://identity.test/login", ""],
            {"auth_type": "login", "login_url": "https://identity.test/login"},
        ),
        (
            ["api-key", "X-Custom-Key"],
            {"auth_type": "api-key", "api_key_header": "X-Custom-Key"},
        ),
        (
            ["oauth2", "https://identity.test/token", "PASSWORD", "client"],
            {
                "auth_type": "oauth2",
                "token_url": "https://identity.test/token",
                "grant_type": "password",
                "client_id": "client",
            },
        ),
        (
            ["oidc", "https://identity.test/realm", "client", "profile email openid"],
            {
                "auth_type": "oidc",
                "issuer_url": "https://identity.test/realm",
                "client_id": "client",
                "scopes": ["openid", "profile", "email"],
            },
        ),
    ],
)
def test_configure_prompts_only_for_public_provider_settings(
    answers, expected, monkeypatch
):
    prompt = Mock(side_effect=["https://processing.test", *answers])
    monkeypatch.setattr("typer.prompt", prompt)
    configure_client_with_prompt()
    assert yaml.safe_load(ClientConfig.default_path.read_text()) == {
        "api_url": "https://processing.test/",
        "auth": expected,
    }
    assert prompt.call_count == len(answers) + 1


def test_configure_reuses_public_values_but_never_secrets(monkeypatch):
    config = ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "token",
            "access_token": "secret",
            "access_token_header": "X-Custom",
        },
    )
    config.write()
    monkeypatch.setattr("typer.prompt", lambda label, **kwargs: kwargs["default"])
    configure_client_with_prompt()
    assert ClientConfig.from_file().to_file_dict() == config.to_file_dict()
    assert "secret" not in ClientConfig.default_path.read_text()


def test_branded_configuration_defaults_are_preserved(monkeypatch):
    class BrandedConfig(ClientConfig):
        api_url: str | None = "https://branded.test"
        service_name: str = "branded"

    prompt = Mock(return_value="https://configured.test")
    monkeypatch.setattr("typer.prompt", prompt)
    configure_client_with_prompt(config_type=BrandedConfig, auth_type="none")
    assert prompt.call_args.kwargs["default"] == "https://branded.test/"
    config = BrandedConfig.from_file()
    assert isinstance(config, BrandedConfig)
    assert config.service_name == "branded"


def test_custom_cli_uses_its_configuration_namespace(tmp_path):
    class BrandedConfig(ClientConfig):
        default_path: ClassVar[Path] = tmp_path / "branded.yaml"
        service_name: str = "branded"

    result = CliRunner().invoke(
        new_cli(name="branded-client", config_type=BrandedConfig),
        [
            "configure",
            "--api-url",
            "https://configured.test/processes",
            "--auth-type",
            "none",
        ],
    )

    assert result.exit_code == 0
    assert not ClientConfig.default_path.exists()
    assert BrandedConfig.from_file().service_name == "branded"


def test_switching_auth_type_does_not_reuse_other_provider_settings(monkeypatch):
    ClientConfig(
        api_url="https://processing.test",
        auth={
            "auth_type": "oidc",
            "issuer_url": "https://old.test/realm",
            "client_id": "old-client",
        },
    ).write()
    prompt = Mock(side_effect=["https://new.test/token", "password", "new-client"])
    monkeypatch.setattr("typer.prompt", prompt)
    configure_client_with_prompt(api_url="https://processing.test", auth_type="oauth2")
    assert prompt.call_args.kwargs["default"] == ""
    assert ClientConfig.from_file().auth.client_id == "new-client"


@pytest.mark.parametrize(
    "old",
    [
        {"auth_type": "token", "token": "OLD-SECRET"},
        {"auth": {"auth_type": "token", "use_bearer": True}},
        {"auth": {"auth_type": "oauth2", "access_token": "OLD-SECRET"}},
        "auth: [OLD-SECRET\n",
        "- OLD-SECRET\n",
    ],
)
def test_incompatible_configuration_is_recreated_without_translation(
    old, monkeypatch, capsys
):
    ClientConfig.default_path.write_text(
        old
        if isinstance(old, str)
        else yaml.safe_dump({"api_url": "https://old.test", **old})
    )
    configure_client_with_prompt(
        api_url="https://new.test", auth_type="token", access_token_header=""
    )
    assert "configuring from defaults" in capsys.readouterr().err
    assert yaml.safe_load(ClientConfig.default_path.read_text()) == {
        "api_url": "https://new.test/",
        "auth": {"auth_type": "token"},
    }
    assert "OLD-SECRET" not in ClientConfig.default_path.read_text()


@pytest.mark.parametrize("command", ["list-processes", "login", "logout"])
@pytest.mark.parametrize("contents", ["auth: [OLD-SECRET\n", "auth_type: unknown\n"])
def test_invalid_file_has_actionable_error_in_custom_cli(command, contents):
    path = ClientConfig.default_path
    path.write_text(contents, encoding="utf-8")
    result = CliRunner().invoke(new_cli(name="sen4cap-client"), [command])
    assert result.exit_code == 1
    assert result.stderr.strip() == (
        "Deprecated or illegal configuration file, please run the 'configure' command."
    )
    assert "OLD-SECRET" not in result.output
    assert path.read_text(encoding="utf-8") == contents


@pytest.mark.parametrize(
    "options,message",
    [
        ({"auth_type": "unknown"}, "Invalid authentication type"),
        (
            {
                "auth_type": "oauth2",
                "token_url": "https://identity.test/token",
                "grant_type": "unknown",
            },
            "Invalid OAuth2 grant type",
        ),
        ({"auth_type": "none", "issuer_url": "https://unused.test"}, "do not apply"),
        (
            {
                "auth_type": "token",
                "access_token_header": "",
                "password": "DO-NOT-ECHO",
            },
            "do not apply",
        ),
    ],
)
def test_invalid_options_do_not_overwrite_existing_configuration(
    options, message, capsys
):
    ClientConfig(api_url="https://original.test").write()
    before = ClientConfig.default_path.read_text()
    with pytest.raises(ValueError, match=message) as error:
        configure_client_with_prompt(api_url="https://new.test", **options)
    assert "DO-NOT-ECHO" not in str(error.value)
    assert ClientConfig.default_path.read_text() == before


def test_explicit_values_override_saved_defaults_without_prompting(monkeypatch):
    ClientConfig(
        api_url="https://old.test",
        auth={"auth_type": "api-key", "api_key_header": "X-Old"},
    ).write()
    prompt = Mock(side_effect=AssertionError("no prompt expected"))
    monkeypatch.setattr("typer.prompt", prompt)
    configure_client_with_prompt(
        api_url="https://new.test", auth_type="API-KEY", api_key_header="X-New"
    )
    assert ClientConfig.from_file().auth.api_key_header == "X-New"
    prompt.assert_not_called()
