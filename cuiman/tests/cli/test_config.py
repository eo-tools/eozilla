#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# ruff: noqa: S105, S106

import os
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
    _configure_auth_with_prompt,
    configure_client_with_prompt,
    get_config,
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

    def test_get_config_rejects_legacy_cli_login_auth(self):
        legacy_config = {
            "api_url": "https://eozilla.example.test",
            "auth_type": "login",
            "auth_url": "https://identity.example.test/token",
            "username": "user",
            "password": "password",
            "client_id": "client",
            "client_secret": "secret",
            "grant_type": "password",
            "token": "access",
            "refresh_token": "refresh",
            "use_bearer": True,
            "token_header": "X-Auth-Token",
            "api_key_header": "X-API-Key",
        }
        ClientConfig.default_path.write_text(yaml.safe_dump(legacy_config))

        with self.assertRaisesRegex(
            ValueError,
            "Legacy configuration format detected, please run 'cuiman configure'",
        ):
            get_config(None)

        self.assertEqual(
            legacy_config, yaml.safe_load(ClientConfig.default_path.read_text())
        )


class ConfigureClientWithPromptTest(ConfigTestMixin, unittest.TestCase):
    def assert_is_default_config_path(self, config_path: Path):
        self.assertEqual(ClientConfig.default_path, config_path)
        self.assertTrue(ClientConfig.default_path.exists())

    def test_none_auth_needs_no_additional_configuration(self):
        context = _Context(cli_params={}, prev_params={}, curr_params={})
        _configure_auth_with_prompt(context, "none")
        self.assertEqual({}, context.curr_params)

    @patch("typer.prompt")
    def test_auth_type_none(self, prompt: MagicMock):
        prompt.side_effect = ["http://localhost:9090", "none"]

        config_path = configure_client_with_prompt()

        self.assert_is_default_config_path(config_path)
        self.assertEqual(
            ClientConfig(api_url="http://localhost:9090", auth=NoAuthConfig()),
            get_config(None),
        )

    @patch("typer.prompt")
    def test_auth_type_invalid(self, prompt: MagicMock):
        prompt.side_effect = ["http://localhost:9090", "torken"]
        with pytest.raises(ValueError, match="Invalid authentication type: torken"):
            configure_client_with_prompt()

    @patch("typer.prompt")
    def test_auth_type_basic(self, prompt: MagicMock):
        prompt.side_effect = [
            "http://localhorst:9999",
            "basic",
            "udo",
            "987",
        ]

        config_path = configure_client_with_prompt()

        self.assert_is_default_config_path(config_path)
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth=BasicAuthConfig(username="udo", password="987"),
            ),
            get_config(None),
        )

    @patch("cuiman.cli.config.login_for_tokens")
    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_auth_type_login(
        self, prompt: MagicMock, confirm: MagicMock, login: MagicMock
    ):
        login.return_value = TokenResult(access_token="dummy-token")
        prompt.side_effect = [
            "http://localhorst:9999",
            "login",
            "http://localhorst:9999/signin",
            "bibo",
            "1234",
            "X-Custom-Token",
        ]
        confirm.return_value = False

        config_path = configure_client_with_prompt()

        self.assert_is_default_config_path(config_path)
        login.assert_called_once()
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth=LoginAuthConfig(
                    login_url="http://localhorst:9999/signin",
                    username="bibo",
                    password="1234",
                    access_token="dummy-token",
                    use_bearer=False,
                    access_token_header="X-Custom-Token",
                ),
            ),
            get_config(None),
        )

    @patch("cuiman.cli.config.obtain_oauth2_tokens")
    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_oauth2_password_grant(
        self, prompt: MagicMock, confirm: MagicMock, obtain: MagicMock
    ):
        obtain.return_value = TokenResult(
            access_token="access", refresh_token="refresh"
        )
        prompt.side_effect = [
            "http://localhorst:9999",
            "oauth2",
            "https://identity.example.test/token",
            "password",
            "bibo",
            "1234",
            "client",
            "secret",
        ]
        confirm.return_value = True

        configure_client_with_prompt()

        obtain.assert_called_once()
        self.assertEqual(
            OAuth2AuthConfig(
                token_url="https://identity.example.test/token",
                username="bibo",
                password="1234",
                client_id="client",
                client_secret="secret",
                access_token="access",
                refresh_token="refresh",
            ),
            get_config(None).auth,
        )

    @patch("cuiman.cli.config.obtain_oauth2_tokens")
    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_oauth2_client_credentials_grant(
        self, prompt: MagicMock, confirm: MagicMock, obtain: MagicMock
    ):
        obtain.return_value = TokenResult(access_token="access")
        prompt.side_effect = [
            "http://localhorst:9999",
            "oauth2",
            "https://identity.example.test/token",
            "client_credentials",
            "client",
            "secret",
        ]
        confirm.return_value = True

        configure_client_with_prompt()

        self.assertEqual(
            OAuth2AuthConfig(
                token_url="https://identity.example.test/token",
                grant_type="client_credentials",
                client_id="client",
                client_secret="secret",
                access_token="access",
            ),
            get_config(None).auth,
        )

    @patch("typer.prompt")
    def test_invalid_oauth2_grant(self, prompt: MagicMock):
        prompt.side_effect = [
            "http://localhorst:9999",
            "oauth2",
            "https://identity.example.test/token",
            "magic",
        ]
        with pytest.raises(ValueError, match="Invalid OAuth2 grant type: magic"):
            configure_client_with_prompt()

    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_auth_type_token(self, prompt: MagicMock, confirm: MagicMock):
        prompt.side_effect = ["http://localhorst:9999", "token", "token-value"]
        confirm.return_value = True

        configure_client_with_prompt()

        self.assertEqual(
            TokenAuthConfig(access_token="token-value"), get_config(None).auth
        )

    @patch("typer.prompt")
    def test_auth_type_api_key(self, prompt: MagicMock):
        prompt.side_effect = [
            "http://localhorst:9999",
            "api-key",
            "key-value",
            "X-API-Key",
        ]

        configure_client_with_prompt()

        self.assertEqual(ApiKeyAuthConfig(api_key="key-value"), get_config(None).auth)

    @patch("typer.prompt")
    def test_prompt_for_pw_reuses_previous_password(self, prompt: MagicMock):
        prompt.side_effect = [
            "http://localhost:9090",
            "basic",
            "alice",
            "secret123",
        ]
        configure_client_with_prompt()

        prompt.reset_mock()
        prompt.side_effect = [
            "http://localhost:9090",
            "basic",
            "alice",
            "******",
        ]
        config_path = configure_client_with_prompt()

        self.assertEqual("secret123", get_config(None).auth.password)
        self.assert_is_default_config_path(config_path)

    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_prompt_for_bool_uses_env_value(
        self, prompt: MagicMock, confirm: MagicMock
    ):
        with patch.dict(
            os.environ,
            {
                "EOZILLA_AUTH__AUTH_TYPE": "token",
                "EOZILLA_AUTH__ACCESS_TOKEN": "environment-token",
                "EOZILLA_AUTH__USE_BEARER": "True",
            },
        ):
            prompt.side_effect = [
                "http://localhost:9090",
                "token",
                "my-token",
            ]
            confirm.return_value = True

            configure_client_with_prompt()

        _, kwargs = confirm.call_args
        self.assertTrue(kwargs["default"])

    @patch("typer.prompt")
    def test_using_custom_config_path(self, prompt: MagicMock):
        prompt.side_effect = ["http://localhost:9090", "none"]
        custom_config_path = Path("my-config.cfg")
        try:
            actual_path = configure_client_with_prompt(config_path=custom_config_path)
            self.assertEqual(custom_config_path, actual_path)
            self.assertEqual(
                ClientConfig(api_url="http://localhost:9090"),
                get_config(custom_config_path),
            )
        finally:
            if custom_config_path.exists():
                os.remove(custom_config_path)
