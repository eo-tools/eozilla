"""Regression tests for source resolution, snapshots, and application schemas."""

# ruff: noqa: S105, S106

import os
from pathlib import Path
from typing import ClassVar, Self
from unittest.mock import Mock, patch

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, Field, model_validator
from pydantic_settings import SettingsConfigDict

from cuiman import AsyncClient, Client, ClientConfig
from cuiman.api.auth import AuthConfig, LoginAuthConfig, TokenAuthConfig
from cuiman.api.config import _set_auth_secret_persistor
from cuiman.cli.config import configure_client_with_prompt, get_config


@pytest.fixture(autouse=True)
def clear_environment(monkeypatch):
    """Keep a developer's default client environment out of resolution probes."""
    for name in os.environ:
        if name.startswith("EOZILLA_"):
            monkeypatch.delenv(name)


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize(
    "overrides", [{}, {"auth": {}}, {"auth": {"access_token": "replacement"}}]
)
def test_snapshot_overrides_never_replay_sources(
    client_type, overrides, tmp_path, monkeypatch
):
    class ApplicationConfig(ClientConfig):
        model_config = SettingsConfigDict(env_prefix="SNAPSHOT_")
        default_path: ClassVar[Path] = tmp_path / "profile"
        region: str = "default-region"
        optional: str | None = None

    original = ApplicationConfig.create(auth=TokenAuthConfig(access_token="original"))
    monkeypatch.setenv("SNAPSHOT_REGION", "changed-environment")
    monkeypatch.setenv("SNAPSHOT_OPTIONAL", "changed-environment")
    ApplicationConfig.default_path.write_text("invalid: [")
    # Even an explicitly repeated profile path refers to the same snapshot.
    wrapped = client_type(
        config=original, config_path=original._source_path, **overrides
    ).config
    assert wrapped.region == "default-region"
    assert wrapped.optional is None
    assert wrapped._source_path == original._source_path
    assert wrapped.auth.access_token == overrides.get("auth", {}).get(
        "access_token", "original"
    )
    assert original.auth.access_token == "original"
    assert wrapped.auth is not original.auth


def test_explicit_new_profile_is_loaded_but_snapshot_values_keep_precedence(tmp_path):
    original = ClientConfig.create(api_url="https://original.test")
    path = tmp_path / "new-profile"
    path.write_text("api_url: https://file.test\n")
    wrapped = ClientConfig.create(config=original, config_path=path)
    assert wrapped._source_path == path
    assert wrapped._has_profile
    assert wrapped.api_url == original.api_url
    path.write_text("invalid: [")
    with pytest.raises(ValueError, match="Deprecated or illegal"):
        ClientConfig.create(config=original, config_path=path)


def test_explicit_default_values_keep_precedence():
    class ApplicationConfig(ClientConfig):
        region: str = "default-region"

    ApplicationConfig.new_instance(region="saved-region").write()
    explicit = ApplicationConfig.new_instance(region="default-region")
    config = ApplicationConfig.create(config=explicit)
    assert config.region == "default-region"


def test_required_fields_and_dependent_factories_validate_after_source_merge():
    validations = []
    factories = []

    def make_label(values):
        factories.append(values["project"])
        return values["project"].upper()

    class ApplicationConfig(ClientConfig):
        project: str
        label: str = Field(default_factory=make_label)

        @model_validator(mode="after")
        def record_validation(self) -> Self:
            validations.append(self.project)
            return self

    config = ApplicationConfig.create(project="supplied")
    assert config.label == "SUPPLIED"
    assert factories == ["supplied"]
    assert validations == ["supplied"]


def test_nested_defaults_and_partial_credentials_merge_without_mutating_inputs():
    class Options(BaseModel):
        region: str = "custom-region"
        retries: int = 2

    class ApplicationConfig(ClientConfig):
        options: Options = Field(default_factory=Options)
        auth: AuthConfig = LoginAuthConfig(
            login_url="https://identity.test/login", access_token_header="X-App"
        )

    overrides = {
        "options": {"retries": 4},
        "auth": {"username": "user", "password": "password"},
    }
    config = ApplicationConfig.create(**overrides)
    assert config.options == Options(retries=4)
    assert str(config.auth.login_url) == "https://identity.test/login"
    assert config.auth.access_token_header == "X-App"
    assert config.auth.username == "user"
    assert overrides["options"] == {"retries": 4}
    assert "auth_type" not in overrides["auth"]
    assert ApplicationConfig.model_fields["auth"].default.username is None


@pytest.mark.parametrize(
    "alias",
    [
        "APP_REGION",
        AliasChoices("APP_REGION", "OLD_REGION"),
        AliasPath("APP", "region"),
    ],
)
def test_aliases_preserve_precedence_and_python_keyword_overrides(
    alias, tmp_path, monkeypatch
):
    dotenv = tmp_path / ".env"
    dotenv.write_text('APP_REGION=dotenv-region\nAPP={"region":"dotenv-region"}\n')

    class ApplicationConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_file=dotenv, dotenv_filtering="only_existing"
        )
        region: str = Field("default-region", validation_alias=alias)

    assert ApplicationConfig.create().region == "dotenv-region"
    monkeypatch.setenv("APP_REGION", "environment-region")
    monkeypatch.setenv("APP", '{"region":"environment-region"}')
    assert ApplicationConfig.create().region == "environment-region"
    assert (
        ApplicationConfig.create(region="explicit-region").region == "explicit-region"
    )
    assert (
        ApplicationConfig.create(
            config=ApplicationConfig.new_instance(region="instance-region")
        ).region
        == "instance-region"
    )


@pytest.mark.parametrize("extra", ["allow", "ignore", "forbid"])
def test_dotenv_namespace_filter_preserves_schema_extra_policy(extra, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "APP_REGION=region\nAPP_EXTENSION=custom\nOTHER_EXTENSION=unrelated\n"
    )

    class ApplicationConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_prefix="APP_", env_file=dotenv, extra=extra
        )
        region: str = "default"

    if extra == "forbid":
        with pytest.raises(ValueError, match="extension"):
            ApplicationConfig.create()
    else:
        config = ApplicationConfig.create()
        assert config.region == "region"
        assert config.model_extra == (
            {"extension": "custom"} if extra == "allow" else None
        )


def test_snapshot_can_load_previously_skipped_secrets_without_reconstructing_settings(
    monkeypatch,
):
    validations = []

    class ApplicationConfig(ClientConfig):
        @model_validator(mode="after")
        def record_validation(self) -> Self:
            validations.append("validate")
            return self

    ApplicationConfig.new_instance(auth=TokenAuthConfig()).write()
    original = ApplicationConfig.create(resolve_secrets=False)
    validations.clear()
    load = Mock(return_value={"access_token": "stored", "unexpected": "ignored"})
    monkeypatch.setattr("cuiman.api.config.load_auth_secrets", load)
    with patch.object(
        ApplicationConfig,
        "read_file_data",
        side_effect=AssertionError("sources replayed"),
    ):
        resolved = ApplicationConfig.create(config=original, resolve_secrets=True)
    assert load.call_count == 1
    assert resolved.auth.access_token == "stored"
    assert original.auth.access_token is None
    assert validations == []  # Only authentication changed; settings stay validated.


def test_snapshot_persistence_is_bound_to_its_own_profile_identity(
    monkeypatch, tmp_path
):
    original = ClientConfig.create(auth=TokenAuthConfig(access_token="original"))
    _set_auth_secret_persistor(original, tmp_path / "original-profile")
    copy = ClientConfig.create(config=original)
    original.api_url = "https://mutated.test/"
    save = Mock()
    monkeypatch.setattr("cuiman.api.config.save_auth_secrets", save)
    copy.auth.persist_secrets()
    save.assert_called_once_with(
        copy._source_path, copy.api_url, "token", {"access_token": "original"}
    )
    changed = ClientConfig.create(config=copy, api_url="https://different.test")
    changed.auth.persist_secrets()
    assert save.call_count == 1


def test_cli_reads_profile_once_and_preserves_custom_public_fields(monkeypatch):
    class ApplicationConfig(ClientConfig):
        project: str
        region: str = "default-region"

    ApplicationConfig.new_instance(project="required", region="saved-region").write()
    with patch.object(
        ApplicationConfig, "read_file_data", wraps=ApplicationConfig.read_file_data
    ) as read:
        assert get_config(None, config_type=ApplicationConfig).project == "required"
    assert read.call_count == 1
    configure_client_with_prompt(
        config_type=ApplicationConfig,
        interactive=False,
        api_url="https://updated.test",
        auth_type="none",
    )
    saved = ApplicationConfig.from_file()
    assert saved.project == "required"
    assert saved.region == "saved-region"
    assert saved.api_url == "https://updated.test/"


def test_configure_accepts_required_provider_fields_and_dictionary_auth_defaults(
    tmp_path,
):
    class RequiredConfig(ClientConfig):
        api_url: str
        auth: AuthConfig

    configure_client_with_prompt(
        config_type=RequiredConfig,
        interactive=False,
        api_url="https://required.test",
        auth_type="none",
    )
    assert RequiredConfig.from_file().api_url == "https://required.test/"

    class DictionaryDefaultConfig(ClientConfig):
        auth: AuthConfig = Field(
            default={"auth_type": "token", "access_token_header": "X-App"}
        )

    path = tmp_path / "dictionary-default"
    with patch("typer.prompt", side_effect=lambda label, **kwargs: kwargs["default"]):
        configure_client_with_prompt(
            config_type=DictionaryDefaultConfig, config_path=path
        )
    assert DictionaryDefaultConfig.from_file(path).auth == TokenAuthConfig(
        access_token_header="X-App"
    )


def test_nested_model_aliases_remain_valid_after_top_level_normalization():
    class Options(BaseModel):
        region: str = Field(validation_alias="REGION")

    class ApplicationConfig(ClientConfig):
        options: Options

    config = ApplicationConfig.create(options={"REGION": "aliased"})
    assert config.options.region == "aliased"
    assert ApplicationConfig.create(config=config).options.region == "aliased"
    assert (
        ApplicationConfig.create(
            config=config, options={"REGION": "updated"}
        ).options.region
        == "updated"
    )

    class WithDefaultConfig(ClientConfig):
        options: Options = Field(default_factory=lambda: Options(REGION="default"))

    assert (
        WithDefaultConfig.create(options={"REGION": "overridden"}).options.region
        == "overridden"
    )


def test_partial_nested_default_factory_receives_validated_preceding_fields():
    calls = []

    class Options(BaseModel):
        timeout: int = 1
        retries: int = 2

    def make_options(values):
        calls.append(values["timeout"])
        return Options(timeout=values["timeout"] * 2)

    class ApplicationConfig(ClientConfig):
        timeout: int = 3
        options: Options = Field(default_factory=make_options)

    assert ApplicationConfig.create(options={"retries": 4}).options == Options(
        timeout=6, retries=4
    )
    assert ApplicationConfig.create(
        timeout="5", options={"retries": 1}
    ).options == Options(timeout=10, retries=1)
    assert calls == [3, 5]


def test_partial_mapping_can_replace_an_absent_default():
    class ApplicationConfig(ClientConfig):
        options: dict[str, int] | None = None

    # There is no mapping default to merge; validate the supplied mapping itself.
    assert ApplicationConfig.create(options={"retries": "4"}).options == {"retries": 4}


@pytest.mark.parametrize(
    "operation",
    [ClientConfig.create, ClientConfig.from_file, ClientConfig.new_instance],
)
def test_invalid_config_type_is_not_reported_as_an_invalid_file(operation):
    with pytest.raises(TypeError, match="config_type must be"):
        operation(config_type=str)
