#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import yaml
from pydantic_settings import SettingsConfigDict

from cuiman.api.auth import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
    TokenResult,
)
from cuiman.api.config import (
    ClientConfig,
    _update_config_from_env,
    _update_if_not_none,
)
from cuiman.api.defaults import DEFAULT_API_URL


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
        self.assertIsNone(config.api_url)
        self.assertEqual(NoAuthConfig(), config.auth)

    def test_create_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config = ClientConfig.create(
                config_path=Path(tmp_dir_name) / "missing-config"
            )
        self.assertEqual(DEFAULT_API_URL, config.api_url)
        self.assertEqual(NoAuthConfig(), config.auth)

    def test_branded_default_config_controls_type_defaults_and_environment(self):
        class BrandedClientConfig(ClientConfig):
            model_config = SettingsConfigDict(
                env_prefix="BRANDED_",
                env_nested_delimiter="__",
                extra="forbid",
            )

            service_name: str = "branded"

        branded_default = BrandedClientConfig(
            api_url="https://default.example.test/processes",
            auth=TokenAuthConfig(use_bearer=False, access_token_header="X-Branded"),
        )
        with patch.dict(
            os.environ,
            {"BRANDED_API_URL": "https://environment.example.test/processes"},
        ):
            with patch.object(ClientConfig, "default_config", branded_default):
                with tempfile.TemporaryDirectory() as tmp_dir_name:
                    config = ClientConfig.create(
                        config_path=Path(tmp_dir_name) / "missing-config"
                    )

        self.assertIsInstance(config, BrandedClientConfig)
        self.assertEqual("https://environment.example.test/processes", config.api_url)
        self.assertEqual(
            TokenAuthConfig(use_bearer=False, access_token_header="X-Branded"),
            config.auth,
        )
        self.assertEqual("branded", config.service_name)

    def test_branded_default_config_loads_files_as_branded_type(self):
        class BrandedClientConfig(ClientConfig):
            service_name: str = "branded"

        branded_default = BrandedClientConfig(
            api_url="https://default.example.test/processes",
            auth=TokenAuthConfig(),
        )
        with patch.object(ClientConfig, "default_config", branded_default):
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
                config = ClientConfig.from_file(config_path)

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

    def test_create_from_file(self):
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
            ),
            config,
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

    @patch("cuiman.api.auth.oauth2.renew_oauth2_tokens")
    @patch("cuiman.api.config.save_auth_secrets")
    @patch("cuiman.api.config.load_auth_secrets")
    def test_keyring_loaded_oauth2_config_persists_refreshed_tokens(
        self, load_auth_secrets, save_auth_secrets, renew_oauth2_tokens
    ):
        load_auth_secrets.return_value = {
            "username": "u",
            "password": "p",
            "access_token": "old-access",
            "refresh_token": "old-refresh",
        }
        renew_oauth2_tokens.return_value = TokenResult(
            access_token="new-access", refresh_token="new-refresh"
        )
        original = ClientConfig(
            api_url="https://eozilla.example.test",
            auth=OAuth2AuthConfig(token_url="https://identity.example.test/token"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            original.write(config_path)
            config = ClientConfig.create(config_path=config_path)
            config.auth.make_token_refresher()()

        save_auth_secrets.assert_called_once_with(
            config_path,
            "https://eozilla.example.test/",
            "oauth2",
            {
                "username": "u",
                "password": "p",
                "access_token": "new-access",
                "refresh_token": "new-refresh",
            },
        )

    def test_from_file_rejects_legacy_flat_auth_configurations(self):
        common = {
            "api_url": "https://eozilla.example.test",
            "api_key_header": "X-API-Key",
            "grant_type": "password",
            "token_header": "X-Auth-Token",
            "use_bearer": True,
        }
        cases = [
            ({"auth_type": "none"}, NoAuthConfig()),
            (
                {
                    "auth_type": "basic",
                    "auth_url": "https://ignored.example.test",
                    "username": "basic-user",
                    "password": "basic-password",
                },
                BasicAuthConfig(
                    username="basic-user",
                    password="basic-password",
                ),
            ),
            (
                {
                    "auth_type": "token",
                    "token": "legacy-token",
                    "use_bearer": False,
                    "token_header": "X-Legacy-Token",
                },
                TokenAuthConfig(
                    access_token="legacy-token",
                    use_bearer=False,
                    access_token_header="X-Legacy-Token",
                ),
            ),
            (
                {
                    "auth_type": "api-key",
                    "api_key": "legacy-key",
                    "api_key_header": "X-Legacy-Key",
                },
                ApiKeyAuthConfig(
                    api_key="legacy-key",
                    api_key_header="X-Legacy-Key",
                ),
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            for index, (legacy_auth, _) in enumerate(cases):
                with self.subTest(auth_type=legacy_auth["auth_type"]):
                    config_path = Path(tmp_dir_name) / f"legacy-{index}.yaml"
                    contents = yaml.safe_dump({**common, **legacy_auth})
                    config_path.write_text(contents)

                    with self.assertRaisesRegex(
                        ValueError,
                        "Legacy configuration format detected, please run 'cuiman configure'",
                    ):
                        ClientConfig.from_file(config_path)
                    self.assertEqual(contents, config_path.read_text())

    def test_from_file_rejects_nested_secret_bearing_auth_configuration(self):
        config_path = Path(tempfile.mkdtemp()) / "config.yaml"
        try:
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "api_url": "https://eozilla.example.test",
                        "auth": {
                            "auth_type": "token",
                            "access_token": "legacy-token",
                        },
                    }
                )
            )

            with self.assertRaisesRegex(
                ValueError,
                "Legacy configuration format detected, please run 'cuiman configure'",
            ):
                ClientConfig.from_file(config_path)
        finally:
            config_path.unlink(missing_ok=True)
            config_path.parent.rmdir()

    def test_from_file_rejects_legacy_login_auth_configuration(self):
        legacy_config = {
            "api_url": "https://eozilla.example.test",
            "auth_type": "login",
            "auth_url": "https://identity.example.test/token",
            "username": "user",
            "password": "password",
        }

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config.yaml"
            contents = yaml.safe_dump(legacy_config)
            config_path.write_text(contents)

            with self.assertRaisesRegex(
                ValueError,
                "Legacy configuration format detected, please run 'cuiman configure'",
            ):
                ClientConfig.from_file(config_path)

            self.assertEqual(contents, config_path.read_text())

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

    def test_default_config(self):
        self.assertIsInstance(ClientConfig.default_config, ClientConfig)
        self.assertEqual(DEFAULT_API_URL, ClientConfig.default_config.api_url)

    def test_update_if_not_none_skips_none(self):
        target = {"value": "original"}
        _update_if_not_none(target, {"value": None})
        self.assertEqual({"value": "original"}, target)

    def test_update_config_from_env_replaces_auth_for_explicit_auth_type(self):
        target = {
            "auth": {
                "auth_type": "login",
                "login_url": "https://file.example.test/login",
                "username": "u",
                "password": "p",
            }
        }

        _update_config_from_env(
            target,
            {"auth": {"auth_type": "token", "access_token": "token"}},
        )

        self.assertEqual(
            {"auth": {"auth_type": "token", "access_token": "token"}},
            target,
        )
