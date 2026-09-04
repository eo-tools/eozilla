#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from cuiman import ClientConfig
from cuiman.api.auth import (
    ApiKeyAuthConfig,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    TokenAuthConfig,
    TokenResult,
)
from cuiman.cli.config import (
    _Context,
    _prompt_for_auth_type,
    configure_client_with_prompt,
    get_config,
    login_client_with_prompt,
    logout_client,
)
from gavicore.util.testing import set_env


# noinspection PyAttributeOutsideInit,PyPep8Naming
class ConfigTestMixin:
    def setUp(self):
        self.restore_env = set_env(
            **{key: None for key in os.environ if key.startswith("EOZILLA_")}
        )

    def tearDown(self):
        self.restore_env()


class GetConfigTest(ConfigTestMixin, unittest.TestCase):
    def test_get_config_custom(self):
        with pytest.raises(
            ValueError,
            match="Configuration file fantasia.cfg not found or empty.",
        ):
            get_config("fantasia.cfg")

    def test_get_config_no_default(self):
        with pytest.raises(
            ValueError,
            match=(
                r"The client tool has not yet been configured; "
                r"please use the 'configure' command to set it up\."
            ),
        ):
            get_config(None)

    def test_get_config_rejects_legacy_auth_configuration(self):
        legacy_config = {
            "api_url": "https://eozilla.example.test",
            "auth_type": "login",
            "auth_url": "https://identity.example.test/token",
            "username": "user",
            "password": "password",
            "token": "access",
        }
        ClientConfig.default_path.write_text(yaml.safe_dump(legacy_config))

        with self.assertRaisesRegex(
            ValueError,
            "Legacy configuration format detected, please run 'cuiman configure'",
        ):
            get_config(None)

    @patch("cuiman.api.config.load_auth_secrets")
    def test_get_config_resolves_keyring_credentials(self, load_auth_secrets):
        load_auth_secrets.return_value = {"access_token": "stored-token"}
        config_path = ClientConfig.default_path
        ClientConfig(
            api_url="https://eozilla.example.test",
            auth=TokenAuthConfig(),
        ).write(config_path)

        config = get_config(None)

        self.assertEqual("stored-token", config.auth.access_token)

    @patch("cuiman.api.config.load_auth_secrets", return_value={})
    def test_get_config_explains_when_login_is_required(
        self, _load_auth_secrets: MagicMock
    ):
        ClientConfig(
            api_url="https://eozilla.example.test",
            auth=TokenAuthConfig(),
        ).write(ClientConfig.default_path)

        with self.assertRaisesRegex(
            ValueError, r"Please log in first using 'cuiman login'\."
        ):
            get_config(None)

    @patch("cuiman.api.config.load_auth_secrets", return_value={})
    def test_get_config_explains_oauth2_client_credentials_requirement(
        self, _load_auth_secrets: MagicMock
    ):
        ClientConfig(
            api_url="https://eozilla.example.test",
            auth=OAuth2AuthConfig(
                token_url="https://identity.example.test/token",
                grant_type="client_credentials",
                client_id="client",
            ),
        ).write(ClientConfig.default_path)

        with self.assertRaisesRegex(
            ValueError, "client_credentials credentials are not configured"
        ):
            get_config(None)


class ConfigureClientWithPromptTest(ConfigTestMixin, unittest.TestCase):
    def assert_is_default_config_path(self, config_path: Path):
        self.assertEqual(ClientConfig.default_path, config_path)
        self.assertTrue(ClientConfig.default_path.exists())

    def test_none_auth_needs_no_additional_configuration(self):
        context = _Context(cli_params={}, prev_params={}, curr_params={})
        config_path = configure_client_with_prompt(
            api_url="http://localhost:9090", auth_type="none"
        )

        self.assertIsInstance(context, _Context)
        self.assert_is_default_config_path(config_path)
        self.assertEqual(
            ClientConfig(api_url="http://localhost:9090", auth=NoAuthConfig()),
            get_config(None),
        )

    @patch("typer.prompt")
    def test_basic_auth_configuration_never_prompts_for_credentials(
        self, prompt: MagicMock
    ):
        prompt.side_effect = ["http://localhorst:9999", "basic"]

        config_path = configure_client_with_prompt()

        self.assert_is_default_config_path(config_path)
        self.assertEqual(
            ClientConfig(api_url="http://localhorst:9999", auth=BasicAuthConfig()),
            ClientConfig.from_file(config_path),
        )
        self.assertEqual(2, prompt.call_count)

    @patch("typer.confirm", return_value=True)
    @patch("typer.prompt")
    def test_login_auth_configuration_writes_only_public_values(
        self, prompt: MagicMock, _confirm: MagicMock
    ):
        prompt.side_effect = [
            "http://localhorst:9999",
            "login",
            "http://localhorst:9999/signin",
        ]

        configure_client_with_prompt()

        self.assertEqual(
            LoginAuthConfig(login_url="http://localhorst:9999/signin"),
            ClientConfig.from_file(ClientConfig.default_path).auth,
        )
        file_data = yaml.safe_load(ClientConfig.default_path.read_text())
        self.assertEqual(
            {
                "auth_type": "login",
                "login_url": "http://localhorst:9999/signin",
                "use_bearer": True,
                "access_token_header": "X-Auth-Token",
            },
            file_data["auth"],
        )

    @patch("typer.confirm", return_value=True)
    @patch("typer.prompt")
    def test_oauth2_configuration_writes_only_public_values(
        self, prompt: MagicMock, _confirm: MagicMock
    ):
        prompt.side_effect = [
            "http://localhorst:9999",
            "oauth2",
            "https://identity.example.test/token",
            "password",
            "client",
        ]

        configure_client_with_prompt()

        self.assertEqual(
            OAuth2AuthConfig(
                token_url="https://identity.example.test/token", client_id="client"
            ),
            ClientConfig.from_file(ClientConfig.default_path).auth,
        )

    @patch("typer.confirm", return_value=False)
    @patch("typer.prompt")
    def test_token_configuration_keeps_public_header_settings(
        self, prompt: MagicMock, _confirm: MagicMock
    ):
        prompt.side_effect = [
            "http://localhorst:9999",
            "token",
            "X-Custom-Token",
        ]

        configure_client_with_prompt()

        self.assertEqual(
            TokenAuthConfig(use_bearer=False, access_token_header="X-Custom-Token"),
            ClientConfig.from_file(ClientConfig.default_path).auth,
        )

    @patch("typer.prompt")
    def test_api_key_configuration_keeps_only_header(self, prompt: MagicMock):
        prompt.side_effect = ["http://localhorst:9999", "api-key", "X-API-Key"]

        configure_client_with_prompt()

        self.assertEqual(
            ApiKeyAuthConfig(), ClientConfig.from_file(ClientConfig.default_path).auth
        )

    def test_configure_rewrites_legacy_file_without_credentials(self):
        config_path = ClientConfig.default_path
        config_path.write_text(
            yaml.safe_dump(
                {
                    "api_url": "https://eozilla.example.test",
                    "auth_type": "token",
                    "token": "legacy-token",
                    "use_bearer": False,
                    "token_header": "X-Legacy-Token",
                }
            )
        )

        with patch("typer.echo") as echo:
            configure_client_with_prompt(
                api_url="https://eozilla.example.test",
                auth_type="token",
                use_bearer=False,
                access_token_header="X-Legacy-Token",
            )

        self.assertTrue(
            "Warning: legacy configuration detected" in echo.call_args.args[0]
        )
        self.assertEqual(
            {
                "api_url": "https://eozilla.example.test/",
                "auth": {
                    "auth_type": "token",
                    "use_bearer": False,
                    "access_token_header": "X-Legacy-Token",
                },
            },
            yaml.safe_load(config_path.read_text()),
        )

    def test_auth_type_invalid(self):
        with pytest.raises(ValueError, match="Invalid authentication type: torken"):
            configure_client_with_prompt(
                api_url="http://localhost:9090", auth_type="torken"
            )

    def test_auth_type_prompt_uses_valid_previous_value_or_oauth2_default(self):
        for previous_auth_type, expected_default in (
            ("api-key", "api-key"),
            ("unrecognized", "oauth2"),
        ):
            with self.subTest(previous_auth_type=previous_auth_type):
                context = _Context(
                    cli_params={},
                    prev_params={"auth_type": previous_auth_type},
                    curr_params={},
                )
                with patch("typer.prompt", return_value="oauth2") as prompt:
                    _prompt_for_auth_type(context)

                self.assertEqual(expected_default, prompt.call_args.kwargs["default"])


class LoginAndLogoutTest(ConfigTestMixin, unittest.TestCase):
    def write_config(self, auth) -> Path:
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            config_path = Path(stream.name)
        self.addCleanup(config_path.unlink, missing_ok=True)
        ClientConfig(api_url="https://eozilla.example.test", auth=auth).write(
            config_path
        )
        return config_path

    @patch("cuiman.cli.config.save_auth_secrets")
    @patch("typer.prompt", side_effect=["alice", "password"])
    def test_login_basic_stores_credentials(
        self, _prompt: MagicMock, save_auth_secrets: MagicMock
    ):
        config_path = self.write_config(BasicAuthConfig())

        login_client_with_prompt(config_path)

        save_auth_secrets.assert_called_once_with(
            config_path,
            "https://eozilla.example.test/",
            "basic",
            {"username": "alice", "password": "password"},
        )

    @patch("cuiman.cli.config.save_auth_secrets")
    @patch("typer.prompt", return_value="token")
    def test_login_token_stores_access_token(
        self, _prompt: MagicMock, save_auth_secrets: MagicMock
    ):
        config_path = self.write_config(TokenAuthConfig())

        login_client_with_prompt(config_path)

        self.assertEqual({"access_token": "token"}, save_auth_secrets.call_args.args[3])

    @patch("cuiman.cli.config.save_auth_secrets")
    @patch("typer.prompt", return_value="api-key")
    def test_login_api_key_stores_api_key(
        self, _prompt: MagicMock, save_auth_secrets: MagicMock
    ):
        config_path = self.write_config(ApiKeyAuthConfig())

        login_client_with_prompt(config_path)

        self.assertEqual({"api_key": "api-key"}, save_auth_secrets.call_args.args[3])

    @patch("cuiman.cli.config.save_auth_secrets")
    @patch("cuiman.cli.config.login_for_tokens")
    @patch("typer.prompt", side_effect=["alice", "password"])
    def test_login_proprietary_stores_credentials_and_token(
        self,
        _prompt: MagicMock,
        login_for_tokens: MagicMock,
        save_auth_secrets: MagicMock,
    ):
        login_for_tokens.return_value = TokenResult(access_token="token")
        config_path = self.write_config(
            LoginAuthConfig(login_url="https://identity.example.test/login")
        )

        login_client_with_prompt(config_path)

        self.assertEqual(
            {"username": "alice", "password": "password", "access_token": "token"},
            save_auth_secrets.call_args.args[3],
        )

    @patch("cuiman.cli.config.save_auth_secrets")
    @patch("cuiman.cli.config.obtain_oauth2_tokens")
    @patch("typer.prompt", side_effect=["alice", "password", "client-secret"])
    def test_login_oauth2_stores_credentials_and_tokens(
        self,
        _prompt: MagicMock,
        obtain_oauth2_tokens: MagicMock,
        save_auth_secrets: MagicMock,
    ):
        obtain_oauth2_tokens.return_value = TokenResult(
            access_token="access", refresh_token="refresh"
        )
        config_path = self.write_config(
            OAuth2AuthConfig(
                token_url="https://identity.example.test/token", client_id="client"
            )
        )

        login_client_with_prompt(config_path)

        self.assertEqual(
            {
                "username": "alice",
                "password": "password",
                "client_secret": "client-secret",
                "access_token": "access",
                "refresh_token": "refresh",
            },
            save_auth_secrets.call_args.args[3],
        )

    @patch("cuiman.cli.config.save_auth_secrets")
    def test_login_rejects_oauth2_client_credentials(
        self, save_auth_secrets: MagicMock
    ):
        config_path = self.write_config(
            OAuth2AuthConfig(
                token_url="https://identity.example.test/token",
                grant_type="client_credentials",
                client_id="client",
            )
        )

        with pytest.raises(ValueError, match="does not support 'cuiman login'"):
            login_client_with_prompt(config_path)

        save_auth_secrets.assert_not_called()

    @patch("cuiman.cli.config.save_auth_secrets")
    def test_login_none_does_not_write_secrets(self, save_auth_secrets: MagicMock):
        config_path = self.write_config(NoAuthConfig())

        login_client_with_prompt(config_path)

        save_auth_secrets.assert_not_called()

    @patch("cuiman.cli.config.delete_auth_secrets")
    def test_logout_deletes_configured_credentials(
        self, delete_auth_secrets: MagicMock
    ):
        config_path = self.write_config(TokenAuthConfig())

        logout_client(config_path)

        delete_auth_secrets.assert_called_once_with(
            config_path, "https://eozilla.example.test/"
        )
