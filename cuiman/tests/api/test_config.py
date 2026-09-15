#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import os
import tempfile
from pathlib import Path
from typing import ClassVar
from unittest import TestCase
from unittest.mock import patch

import pytest
import yaml
from pydantic_settings import SettingsConfigDict

from cuiman import AsyncClient, Client
from cuiman.api.auth import (
    AuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OidcAuthConfig,
    TokenAuthConfig,
)
from cuiman.api.config import (
    ClientConfig,
    _update_config,
    _update_if_not_none,
)
from cuiman.api.defaults import DEFAULT_API_URL
from cuiman.api.opener import JobResultOpenerRegistry

from ..helpers import AllOpener


class ClientConfigTest(TestCase):
    def setUp(self):
        self.saved_environ = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("EOZILLA_")
        }
        for key in self.saved_environ:
            del os.environ[key]

    def tearDown(self):
        for key in tuple(os.environ):
            if key.startswith("EOZILLA_"):
                del os.environ[key]
        os.environ.update(self.saved_environ)

    def test_ctor(self):
        config = ClientConfig()
        self.assertEqual(DEFAULT_API_URL, config.api_url)
        self.assertEqual(NoAuthConfig(), config.auth)

    def test_create_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config = ClientConfig.create(
                config_path=Path(tmp_dir_name) / "missing-config"
            )
        self.assertEqual(DEFAULT_API_URL, config.api_url)
        self.assertEqual(NoAuthConfig(), config.auth)

    def test_read_file_data_handles_empty_and_non_mapping_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config_path.write_text("")
            self.assertIsNone(ClientConfig.read_file_data(config_path))

            config_path.write_text("- not-a-mapping\n")
            with self.assertRaisesRegex(
                ValueError, "Configuration file must contain a mapping."
            ):
                ClientConfig.read_file_data(config_path)

    def test_config_type_controls_defaults_and_environment(self):
        class BrandedClientConfig(ClientConfig):
            model_config = SettingsConfigDict(
                env_prefix="BRANDED_",
                env_nested_delimiter="__",
                extra="forbid",
            )

            api_url: str | None = "https://default.example.test/processes"
            auth: AuthConfig = TokenAuthConfig(access_token_header="X-Branded")
            service_name: str = "branded"

        with patch.dict(
            os.environ,
            {"BRANDED_API_URL": "https://environment.example.test/processes"},
        ):
            with tempfile.TemporaryDirectory() as tmp_dir_name:
                config = ClientConfig.create(
                    config_type=BrandedClientConfig,
                    config_path=Path(tmp_dir_name) / "missing-config",
                )

        self.assertIsInstance(config, BrandedClientConfig)
        self.assertEqual("https://environment.example.test/processes", config.api_url)
        self.assertEqual(
            TokenAuthConfig(access_token_header="X-Branded"),
            config.auth,
        )
        self.assertEqual("branded", config.service_name)

    def test_config_type_loads_files_with_selected_schema(self):
        class BrandedClientConfig(ClientConfig):
            service_name: str = "branded"

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "api_url": "https://configured.example.test/processes",
                        "auth": {"auth_type": "none"},
                        "service_name": "configured",
                    }
                )
            )
            config = ClientConfig.from_file(
                config_path, config_type=BrandedClientConfig
            )

        self.assertIsInstance(config, BrandedClientConfig)
        self.assertEqual("configured", config.service_name)

    def test_create_from_env(self):
        os.environ.update(
            {
                "EOZILLA_API_URL": "https://eozilla.example.test",
                "EOZILLA_AUTH__AUTH_TYPE": "login",
                "EOZILLA_AUTH__LOGIN_URL": "https://eozilla.example.test/auth/login",
                "EOZILLA_AUTH__USERNAME": "pippo",
                "EOZILLA_AUTH__PASSWORD": "poppi",
                "EOZILLA_AUTH__ACCESS_TOKEN": "0f8915a4",
            }
        )

        config = ClientConfig()

        self.assertEqual("https://eozilla.example.test/", config.api_url)
        self.assertIsInstance(config.auth, LoginAuthConfig)
        self.assertEqual("pippo", config.auth.username)
        self.assertEqual("poppi", config.auth.password)
        self.assertEqual("0f8915a4", config.auth.access_token)

    def test_new_instance_kwargs_override_settings_sources(self):
        os.environ.update(
            {
                "EOZILLA_API_URL": "https://environment.example.test",
                "EOZILLA_AUTH__AUTH_TYPE": "token",
                "EOZILLA_AUTH__ACCESS_TOKEN": "environment-token",
            }
        )

        config = ClientConfig.new_instance(
            api_url="https://explicit.example.test",
            auth={"auth_type": "none"},
        )

        self.assertEqual("https://explicit.example.test/", config.api_url)
        self.assertEqual(NoAuthConfig(), config.auth)

    @patch("cuiman.api.config.load_auth_secrets", return_value={})
    def test_create_from_file(self, _load_auth_secrets):
        original = ClientConfig(
            api_url="https://eozilla.example.test",
            auth=LoginAuthConfig(
                login_url="https://eozilla.example.test/login",
                username="u",
                password="p",
                access_token="token",
            ),
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            config = ClientConfig.create(config_path=config_path)

        self.assertEqual(
            ClientConfig(
                api_url="https://eozilla.example.test",
                auth=LoginAuthConfig(login_url="https://eozilla.example.test/login"),
            ).model_dump(),
            config.model_dump(),
        )

    @patch("cuiman.api.config.load_auth_secrets")
    def test_create_loads_auth_secrets_from_keyring(self, load_auth_secrets):
        original = ClientConfig(
            api_url="https://eozilla.example.test",
            auth=LoginAuthConfig(login_url="https://eozilla.example.test/login"),
        )
        load_auth_secrets.return_value = {
            "username": "u",
            "password": "p",
            "access_token": "token",
        }
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            config = ClientConfig.create(config_path=config_path)

        self.assertIsInstance(config.auth, LoginAuthConfig)
        self.assertEqual("u", config.auth.username)
        self.assertEqual("p", config.auth.password)
        self.assertEqual("token", config.auth.access_token)
        load_auth_secrets.assert_called_once_with(
            config_path,
            "https://eozilla.example.test/",
            "login",
        )

    @patch("cuiman.api.config.load_auth_secrets")
    def test_create_can_skip_keyring_and_preserve_environment_overrides(
        self, load_auth_secrets
    ):
        original = ClientConfig(
            api_url="https://eozilla.example.test", auth=TokenAuthConfig()
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            os.environ["EOZILLA_API_URL"] = "https://override.example.test"
            config = ClientConfig.create(config_path=config_path, resolve_secrets=False)

        self.assertEqual("https://override.example.test/", config.api_url)
        self.assertIsInstance(config.auth, TokenAuthConfig)
        self.assertIsNone(config.auth.access_token)
        load_auth_secrets.assert_not_called()

    @patch("cuiman.api.config.load_auth_secrets")
    def test_environment_secret_overrides_do_not_require_keyring(
        self, load_auth_secrets
    ):
        original = ClientConfig(
            api_url="https://eozilla.example.test",
            auth=TokenAuthConfig(),
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            os.environ["EOZILLA_AUTH__ACCESS_TOKEN"] = "environment-token"
            config = ClientConfig.create(config_path=config_path)

        self.assertEqual("environment-token", config.auth.access_token)
        load_auth_secrets.assert_not_called()

    @patch("cuiman.api.config.load_auth_secrets")
    def test_environment_secret_overrides_keyring_value(self, load_auth_secrets):
        original = ClientConfig(
            api_url="https://eozilla.example.test",
            auth=LoginAuthConfig(login_url="https://eozilla.example.test/login"),
        )
        load_auth_secrets.return_value = {
            "username": "u",
            "password": "keyring-password",
            "access_token": "token",
        }
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            os.environ["EOZILLA_AUTH__PASSWORD"] = "environment-password"
            config = ClientConfig.create(config_path=config_path)

        self.assertEqual("environment-password", config.auth.password)

    def test_create_merges_nested_auth_overrides(self):
        original = ClientConfig(
            api_url="https://eozilla.example.test",
            auth=LoginAuthConfig(
                login_url="https://eozilla.example.test/login",
                username="u",
                password="p",
                access_token="old-token",
            ),
        )

        config = ClientConfig.create(
            config=original,
            auth={"access_token": "new-token"},
        )

        self.assertIsInstance(config.auth, LoginAuthConfig)
        self.assertEqual("new-token", config.auth.access_token)
        self.assertEqual("u", config.auth.username)

    def test_create_from_env_and_file(self):
        os.environ["EOZILLA_API_URL"] = "https://environment.example.test"
        original = ClientConfig(api_url="https://file.example.test")
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            config = ClientConfig.create(config_path=config_path)

        self.assertEqual("https://environment.example.test/", config.api_url)

    def test_partial_nested_env_auth_override_is_merged_with_file(self):
        original = ClientConfig(
            api_url="https://file.example.test",
            auth=LoginAuthConfig(
                login_url="https://file.example.test/login",
                username="u",
                password="p",
                access_token="file-token",
            ),
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            os.environ["EOZILLA_AUTH__ACCESS_TOKEN"] = "environment-token"
            config = ClientConfig.create(config_path=config_path)

        self.assertIsInstance(config.auth, LoginAuthConfig)
        self.assertEqual("environment-token", config.auth.access_token)
        self.assertIsNone(config.auth.username)

    def test_env_auth_type_selects_token_auth_over_file_config(self):
        os.environ.update(
            {
                "EOZILLA_AUTH__AUTH_TYPE": "token",
                "EOZILLA_AUTH__ACCESS_TOKEN": "abc",
            }
        )
        file_configs = [
            {
                "api_url": "https://file.example.test/",
                "auth": {"auth_type": "none"},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            for index, file_config in enumerate(file_configs):
                with self.subTest(file_config=file_config):
                    config_path = Path(tmp_dir_name) / f"config-{index}.yaml"
                    config_path.write_text(yaml.safe_dump(file_config))

                    config = ClientConfig.create(config_path=config_path)

                    self.assertEqual(TokenAuthConfig(access_token="abc"), config.auth)

    def test_env_auth_type_replaces_file_auth_fields(self):
        os.environ.update(
            {
                "EOZILLA_AUTH__AUTH_TYPE": "token",
                "EOZILLA_AUTH__ACCESS_TOKEN": "environment-token",
            }
        )
        original = ClientConfig(
            auth=LoginAuthConfig(
                login_url="https://file.example.test/login",
                username="u",
                password="p",
                access_token="file-token",
            )
        )

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)

            config = ClientConfig.create(config_path=config_path)

        self.assertEqual(TokenAuthConfig(access_token="environment-token"), config.auth)

    def test_normalize_config_path(self):
        path = Path("i/am/a/path")
        self.assertIs(path, ClientConfig.normalize_config_path(path))
        self.assertEqual(path, ClientConfig.normalize_config_path(str(path)))
        self.assertEqual(
            ClientConfig.default_path, ClientConfig.normalize_config_path("")
        )

    def test_field_defaults(self):
        self.assertEqual(DEFAULT_API_URL, ClientConfig.new_instance().api_url)

    def test_update_if_not_none_skips_none(self):
        target = {"value": "original"}
        _update_if_not_none(target, {"value": None})
        self.assertEqual({"value": "original"}, target)

    def test_update_config_replaces_auth_for_explicit_auth_type(self):
        target = {
            "auth": {
                "auth_type": "login",
                "login_url": "https://file.example.test/login",
                "username": "u",
                "password": "p",
            }
        }

        _update_config(
            target,
            {"auth": {"auth_type": "token", "access_token": "token"}},
        )

        self.assertEqual(
            {"auth": {"auth_type": "token", "access_token": "token"}},
            target,
        )


def test_config_namespaces_coexist_with_independent_sources(tmp_path, monkeypatch):
    """Each selected class owns paths, schemas, and its settings namespace."""

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "RED_API_URL=https://dotenv.red.test/processes\n"
        "BLUE_API_URL=https://dotenv.blue.test/processes\n",
        encoding="utf-8",
    )

    class RedConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_prefix="RED_",
            env_nested_delimiter="__",
            env_file=dotenv_path,
            extra="forbid",
        )

        default_path: ClassVar[Path] = tmp_path / "red.yaml"
        api_url: str | None = "https://default.red.test/processes"
        application: str = "red"

    class BlueConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_prefix="BLUE_",
            env_nested_delimiter="__",
            env_file=dotenv_path,
            extra="forbid",
        )

        default_path: ClassVar[Path] = tmp_path / "blue.yaml"
        api_url: str | None = "https://default.blue.test/processes"
        application: str = "blue"

    RedConfig.new_instance(api_url="https://file.red.test/processes").write()
    BlueConfig.new_instance(api_url="https://file.blue.test/processes").write()
    monkeypatch.setenv("RED_API_URL", "https://environment.red.test/processes")

    red = ClientConfig.create(config_type=RedConfig)
    blue = ClientConfig.create(config_type=BlueConfig)

    assert red.api_url == "https://environment.red.test/processes"
    assert blue.api_url == "https://dotenv.blue.test/processes"
    assert red.application == "red"
    assert blue.application == "blue"
    assert red._source_path == RedConfig.default_path
    assert blue._source_path == BlueConfig.default_path
    assert type(Client(config_type=RedConfig).config) is RedConfig
    assert type(AsyncClient(config_type=BlueConfig).config) is BlueConfig


def test_explicit_overrides_win_over_environment_and_dotenv(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "APPLICATION_API_URL=https://dotenv.test/processes\n", encoding="utf-8"
    )

    class ApplicationConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_prefix="APPLICATION_",
            env_nested_delimiter="__",
            env_file=dotenv_path,
            extra="forbid",
        )

    monkeypatch.setenv("APPLICATION_API_URL", "https://environment.test/processes")

    config = ApplicationConfig.create(api_url="https://explicit.test/processes")

    assert config.api_url == "https://explicit.test/processes"


def test_dotenv_partial_auth_override_is_merged_before_validation(tmp_path):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "APPLICATION_AUTH__ACCESS_TOKEN=dotenv-token\n", encoding="utf-8"
    )

    class ApplicationConfig(ClientConfig):
        model_config = SettingsConfigDict(
            env_prefix="APPLICATION_",
            env_nested_delimiter="__",
            env_file=dotenv_path,
            extra="forbid",
        )

    profile_path = tmp_path / "profile.yaml"
    ApplicationConfig.new_instance(auth=TokenAuthConfig()).write(profile_path)

    config = ApplicationConfig.create(config_path=profile_path)

    assert config.auth == TokenAuthConfig(access_token="dotenv-token")


def test_config_type_is_inferred_from_instances_and_requires_exact_match():
    class ParentConfig(ClientConfig):
        pass

    class ChildConfig(ParentConfig):
        pass

    child = ChildConfig.new_instance()

    assert type(ClientConfig.create(config=child)) is ChildConfig
    with pytest.raises(TypeError, match="same concrete"):
        ClientConfig.create(config=child, config_type=ParentConfig)


def test_application_extension_mappings_and_opener_registries_are_isolated():
    class FirstConfig(ClientConfig):
        pass

    class SecondConfig(ClientConfig):
        pass

    assert FirstConfig.return_type_map is not ClientConfig.return_type_map
    assert SecondConfig.return_type_map is not ClientConfig.return_type_map
    assert FirstConfig.return_type_map is not SecondConfig.return_type_map
    assert FirstConfig.get_job_result_opener_registry() is not (
        SecondConfig.get_job_result_opener_registry()
    )


@pytest.mark.parametrize("iterable_type", [list, tuple, iter])
def test_declared_job_result_openers_are_registered_once(iterable_type):
    class LastOpener(AllOpener):
        pass

    class ApplicationConfig(ClientConfig):
        extra_job_result_openers = iterable_type([AllOpener, LastOpener])

    registry = ApplicationConfig.get_job_result_opener_registry()
    defaults = JobResultOpenerRegistry.create_default().opener_types
    assert registry.opener_types == (LastOpener, AllOpener, *defaults)
    assert ApplicationConfig.get_job_result_opener_registry() is registry

    unregister = ApplicationConfig.register_job_result_opener(AllOpener)
    assert registry.opener_types == (AllOpener, LastOpener, *defaults)
    unregister()
    assert ApplicationConfig.get_job_result_opener_registry().opener_types == (
        LastOpener,
        *defaults,
    )


@pytest.mark.parametrize("iterable_type", [list, tuple, iter])
def test_declared_job_result_openers_are_inherited_and_isolated(iterable_type):
    class OtherOpener(AllOpener):
        pass

    declared_openers = [AllOpener]

    class ParentConfig(ClientConfig):
        extra_job_result_openers = iterable_type(declared_openers)

    class ChildConfig(ParentConfig):
        pass

    class OverrideConfig(ParentConfig):
        extra_job_result_openers = [OtherOpener]

    class EmptyConfig(ParentConfig):
        extra_job_result_openers = ()

    class UnrelatedConfig(ClientConfig):
        pass

    base_openers = ClientConfig.get_job_result_opener_registry().opener_types
    defaults = JobResultOpenerRegistry.create_default().opener_types
    declared_openers.append(OtherOpener)
    parent_registry = ParentConfig.get_job_result_opener_registry()
    assert parent_registry.opener_types == (AllOpener, *defaults)
    ParentConfig.register_job_result_opener(OtherOpener)
    assert parent_registry.opener_types == (OtherOpener, AllOpener, *defaults)
    parent_registry.clear()
    assert ChildConfig.get_job_result_opener_registry().opener_types == (
        AllOpener,
        *defaults,
    )
    assert OverrideConfig.get_job_result_opener_registry().opener_types == (
        OtherOpener,
        *defaults,
    )
    assert EmptyConfig.get_job_result_opener_registry().opener_types == defaults
    assert UnrelatedConfig.get_job_result_opener_registry().opener_types == defaults
    assert ClientConfig.get_job_result_opener_registry().opener_types == base_openers
    assert ClientConfig.extra_job_result_openers == ()


def test_declared_job_result_openers_are_not_settings(tmp_path):
    class ApplicationConfig(ClientConfig):
        extra_job_result_openers = [AllOpener]

    config = ApplicationConfig.create()
    assert "extra_job_result_openers" not in ApplicationConfig.model_fields
    assert (
        "extra_job_result_openers"
        not in ApplicationConfig.model_json_schema()["properties"]
    )
    assert "extra_job_result_openers" not in config.model_dump()
    path = config.write(tmp_path / "config.yaml")
    assert "extra_job_result_openers" not in path.read_text()
    restored = ApplicationConfig.from_file(path)
    assert restored.extra_job_result_openers == (AllOpener,)


def test_declared_job_result_openers_are_validated():
    class ApplicationConfig(ClientConfig):
        extra_job_result_openers = [int]

    with pytest.raises(
        TypeError, match="Type compatible with JobResultOpener expected"
    ):
        ApplicationConfig.get_job_result_opener_registry()


@pytest.fixture
def saved_login_config():
    path = ClientConfig.default_path
    ClientConfig.new_instance(
        api_url="http://localhost:8080/process/",
        auth={
            "auth_type": "login",
            "login_url": "http://localhost:8080/auth/login",
            "access_token_header": "X-Saved-Token",
        },
    ).write(path)
    return path


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
@pytest.mark.parametrize("source", ["kwargs", "auth_model", "config"])
def test_explicit_oidc_replaces_saved_login_auth(
    saved_login_config, client_type, source
):
    auth = {
        "auth_type": "oidc",
        "issuer_url": "https://identity.example.test/realms/eozilla-auth",
        "client_id": "cuiman",
    }
    values = {"api_url": "https://processing.example.test/", "auth": auth}
    if source == "auth_model":
        values["auth"] = OidcAuthConfig(**auth)
    elif source == "config":
        values = {"config": ClientConfig.new_instance(**values)}

    with patch("cuiman.api.config.load_auth_secrets", return_value={}):
        client = client_type(**values)

    assert client.config.api_url == "https://processing.example.test/"
    assert client.config.auth.model_dump() == OidcAuthConfig(**auth).model_dump()
    assert client._transport is None
    assert ClientConfig.from_file(saved_login_config).auth.auth_type == "login"


@pytest.mark.parametrize("source", ["kwargs", "config", "environment"])
def test_selected_auth_keeps_keyring_credentials_on_resolution(
    saved_login_config, monkeypatch, source
):
    auth = {
        "auth_type": "oidc",
        "issuer_url": "https://identity.example.test/realms/eozilla-auth",
        "client_id": "cuiman",
    }
    values = {"auth": auth}
    if source == "config":
        values = {"config": ClientConfig.new_instance(**values)}
    elif source == "environment":
        for name, value in auth.items():
            monkeypatch.setenv(f"EOZILLA_AUTH__{name.upper()}", value)
        values = {}
    secrets = {
        "oauth_token": '{"access_token":"stored-access","refresh_token":"stored-refresh"}'
    }

    with patch("cuiman.api.config.load_auth_secrets", return_value=secrets) as load:
        config = ClientConfig.create(**values)

    assert config.auth.model_dump() == OidcAuthConfig(**auth, **secrets).model_dump()
    load.assert_called_once_with(
        saved_login_config, "http://localhost:8080/process/", "oidc"
    )


def test_explicit_auth_type_resets_fields_even_when_type_is_unchanged(
    saved_login_config,
):
    with patch("cuiman.api.config.load_auth_secrets", return_value={}):
        config = ClientConfig.create(
            auth={"auth_type": "login", "login_url": "https://new.example.test/login"}
        )

    assert (
        config.auth.model_dump()
        == LoginAuthConfig(login_url="https://new.example.test/login").model_dump()
    )


def test_file_auth_replaces_selected_application_default_auth(tmp_path):
    class ApplicationConfig(ClientConfig):
        auth: AuthConfig = LoginAuthConfig(
            login_url="https://default.example.test/login"
        )

    path = tmp_path / "profile.yaml"
    path.write_text("auth:\n  auth_type: none\n")

    assert ApplicationConfig.create(config_path=path).auth == NoAuthConfig()


@pytest.mark.parametrize("source", ["kwargs", "config"])
def test_explicit_auth_replaces_environment_credentials(
    saved_login_config, monkeypatch, source
):
    monkeypatch.setenv("EOZILLA_AUTH__AUTH_TYPE", "login")
    monkeypatch.setenv("EOZILLA_AUTH__LOGIN_URL", "https://env.example.test/login")
    monkeypatch.setenv("EOZILLA_AUTH__ACCESS_TOKEN", "environment-token")
    values = {"auth": {"auth_type": "none"}}
    if source == "config":
        values = {"config": ClientConfig.new_instance(**values)}

    config = ClientConfig.create(**values)

    assert config.auth == NoAuthConfig()
    assert config.auth.auth_headers == {}


@pytest.mark.parametrize(
    "contents",
    [
        "auth: [\n  OLD-SECRET\n",
        "- OLD-SECRET\n",
        "1: OLD-SECRET\n",
        "auth_type: token\ntoken: OLD-SECRET\n",
        "auth:\n  access_token: OLD-SECRET\n",
        "auth:\n  auth_type: login\n  username: OLD-SECRET\n",
        "auth:\n  auth_type: token\n  token_header: OLD-SECRET\n",
        "api_url: OLD-SECRET\n",
        "auth:\n  auth_type: oauth2\n  token_url: https://identity.test/token\n  client_id: client\n  oauth_token: OLD-SECRET\n",
    ],
)
def test_from_file_reports_invalid_configuration_without_exposing_contents(
    tmp_path, contents
):
    path = tmp_path / "config.yaml"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        ClientConfig.from_file(path)
    assert str(error.value) == (
        "Deprecated or illegal configuration file, please run the 'configure' command."
    )
    assert error.value.__suppress_context__
    assert path.read_text(encoding="utf-8") == contents


def test_from_file_accepts_valid_auth_credentials_without_rewriting(tmp_path):
    path = tmp_path / "config.yaml"
    contents = "auth:\n  auth_type: token\n  access_token: saved-token\n"
    path.write_text(contents, encoding="utf-8")
    config = ClientConfig.from_file(path)
    assert config.auth == TokenAuthConfig(access_token="saved-token")
    assert path.read_text(encoding="utf-8") == contents
    assert "access_token" not in config.to_file_dict()["auth"]


def test_from_file_uses_custom_schema_without_legacy_field_detection(
    tmp_path,
):
    class CustomConfig(ClientConfig):
        model_config = SettingsConfigDict(extra="allow")

    path = tmp_path / "config.yaml"
    path.write_text("auth_type: custom-extension\n", encoding="utf-8")
    config = ClientConfig.from_file(path, config_type=CustomConfig)
    assert isinstance(config, CustomConfig)
    assert config.model_extra == {"auth_type": "custom-extension"}


def test_from_file_preserves_file_access_errors(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("auth: {}", encoding="utf-8")
    with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
        with pytest.raises(PermissionError, match="Access denied"):
            ClientConfig.from_file(path)
