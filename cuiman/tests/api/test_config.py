#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import os
import tempfile
from pathlib import Path
from unittest import TestCase

import yaml

from cuiman.api.auth import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    TokenAuthConfig,
)
from cuiman.api.config import ClientConfig, _update_if_not_none
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

        self.assertEqual(original, config)

    def test_from_file_converts_legacy_flat_auth_configurations(self):
        common = {
            "api_url": "https://eozilla.example.test",
            "api_key_header": "X-API-Key",
            "grant_type": "password",
            "token_header": "X-Auth-Token",
            "use_bearer": True,
        }
        cases = [
            (
                {"auth_type": "none"},
                NoAuthConfig(),
            ),
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
            for index, (legacy_auth, expected_auth) in enumerate(cases):
                with self.subTest(auth_type=legacy_auth["auth_type"]):
                    config_path = Path(tmp_dir_name) / f"legacy-{index}.yaml"
                    contents = yaml.safe_dump({**common, **legacy_auth})
                    config_path.write_text(contents)

                    config = ClientConfig.from_file(config_path)

                    self.assertIsNotNone(config)
                    self.assertEqual(expected_auth, config.auth)
                    self.assertEqual(contents, config_path.read_text())

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
        self.assertEqual("u", config.auth.username)

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
