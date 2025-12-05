#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

from cuiman import ClientConfig
from cuiman.api.defaults import DEFAULT_CONFIG_PATH
from cuiman.cli.config import configure_client_with_prompt, get_config
from gavicore.util.testing import set_env, set_env_cm

DEFAULT_CONFIG_BACKUP_PATH = DEFAULT_CONFIG_PATH.parent / (
    str(DEFAULT_CONFIG_PATH.name) + ".backup"
)


# noinspection PyAttributeOutsideInit,PyPep8Naming
class ConfigTestMixin:
    def setUp(self):
        self.restore_env = set_env(
            **{k: None for k, v in os.environ.items() if k.startswith("EOZILLA_")}
        )
        self.must_restore_config = False
        # If a config backup exists, delete it
        if DEFAULT_CONFIG_BACKUP_PATH.exists():
            os.remove(DEFAULT_CONFIG_BACKUP_PATH)
        # If default config exists, rename it into the backup config
        if DEFAULT_CONFIG_PATH.exists():
            DEFAULT_CONFIG_PATH.rename(DEFAULT_CONFIG_BACKUP_PATH)

    def tearDown(self):
        self.restore_env()
        # If config backup exists, rename it into the default
        if DEFAULT_CONFIG_BACKUP_PATH.exists():
            # If default config exists, remove it,
            # so we can rename the backup
            if DEFAULT_CONFIG_PATH.exists():
                os.remove(DEFAULT_CONFIG_PATH)
            DEFAULT_CONFIG_BACKUP_PATH.rename(DEFAULT_CONFIG_PATH)


class GetConfigTest(ConfigTestMixin, unittest.TestCase):
    # noinspection PyMethodMayBeStatic
    def test_get_config_custom(self):
        with pytest.raises(
            click.ClickException,
            match="Configuration file fantasia.cfg not found or empty.",
        ):
            get_config("fantasia.cfg")

    # noinspection PyMethodMayBeStatic
    def test_get_config_no_default(self):
        with pytest.raises(
            click.ClickException,
            match=(
                r"The client tool has not yet been configured; "
                r"please use the 'configure' command to set it up\."
            ),
        ):
            get_config(None)


class ConfigureClientWithPromptTest(ConfigTestMixin, unittest.TestCase):
    def assert_is_default_config_path(self, config_path: Path):
        self.assertEqual(DEFAULT_CONFIG_PATH, config_path)
        self.assertTrue(DEFAULT_CONFIG_PATH.exists())

    @patch("typer.prompt")
    def test_auth_type_none(self, mock_prompt: MagicMock):
        # Simulate sequential responses to typer.prompt()
        mock_prompt.side_effect = [
            "http://localhost:9090",
            "none",
        ]
        config_path = configure_client_with_prompt()
        self.assertEqual(2, mock_prompt.call_count)
        self.assert_is_default_config_path(config_path)
        config = get_config(None)
        self.assertEqual(
            ClientConfig(api_url="http://localhost:9090", auth_type="none"),
            config,
        )

    @patch("typer.prompt")
    def test_auth_type_basic(self, mock_prompt: MagicMock):
        # Simulate sequential responses to typer.prompt()
        mock_prompt.side_effect = [
            "http://localhorst:9999",  # api_url
            "basic",  # auth_type
            "udo",  # username
            "987",  # password
        ]
        actual_config_path = configure_client_with_prompt()
        self.assertEqual(4, mock_prompt.call_count)
        self.assert_is_default_config_path(actual_config_path)
        config = get_config(None)
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth_type="basic",
                username="udo",
                password="987",
            ),
            config,
        )

    @patch("cuiman.cli.config.login", return_value="dummy-token")
    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_auth_type_login(
        self, mock_prompt: MagicMock, mock_confirm: MagicMock, mock_login: MagicMock
    ):
        # Simulate sequential responses to typer.prompt()
        mock_prompt.side_effect = [
            "http://localhorst:9999",
            "login",
            "http://localhorst:9999/signin",
            "bibo",
            "1234",
            "X-Auth-Token",
        ]
        # Simulate response to typer.confirm()
        mock_confirm.side_effect = [
            False,
        ]
        actual_config_path = configure_client_with_prompt()
        mock_login.assert_called_once()
        mock_confirm.assert_called_once()
        self.assertEqual(6, mock_prompt.call_count)
        self.assert_is_default_config_path(actual_config_path)
        config = get_config(None)
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth_type="login",
                auth_url="http://localhorst:9999/signin",
                username="bibo",
                password="1234",
                token="dummy-token",
                use_bearer=False,
                token_header="X-Auth-Token",
            ),
            config,
        )

    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_auth_type_token(self, mock_prompt: MagicMock, mock_confirm: MagicMock):
        # Simulate sequential responses to typer.prompt()
        mock_prompt.side_effect = [
            "http://localhorst:9999",
            "token",
            "phu-8934kmnl24509kl209245902jk",
        ]
        # Simulate response to typer.confirm()
        mock_confirm.side_effect = [
            True,
        ]
        actual_config_path = configure_client_with_prompt()
        mock_confirm.assert_called_once()
        self.assertEqual(3, mock_prompt.call_count)
        self.assert_is_default_config_path(actual_config_path)
        config = get_config(None)
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth_type="token",
                token="phu-8934kmnl24509kl209245902jk",
                use_bearer=True,
                token_header="X-Auth-Token",
            ),
            config,
        )

    @patch("typer.prompt")
    def test_auth_type_api_key(self, mock_prompt: MagicMock):
        # Simulate sequential responses to typer.prompt()
        mock_prompt.side_effect = [
            "http://localhorst:9999",
            "api-key",
            "AB4E2629967EF3DDE",
            "X-API-Key",
        ]
        actual_config_path = configure_client_with_prompt()
        self.assertEqual(4, mock_prompt.call_count)
        self.assert_is_default_config_path(actual_config_path)
        config = get_config(None)
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth_type="api-key",
                api_key="AB4E2629967EF3DDE",
                api_key_header="X-API-Key",
            ),
            config,
        )

    @patch("cuiman.cli.config.login", return_value="dummy-token")
    @patch("typer.confirm")
    @patch("typer.prompt")
    def test_defaults_are_used(
        self, mock_prompt: MagicMock, mock_confirm: MagicMock, mock_login: MagicMock
    ):
        # Use default password "9823hc!"
        expected_password = "9823hc!"
        with set_env_cm(EOZILLA_PASSWORD=expected_password):
            # Simulate sequential responses to typer.prompt()
            mock_prompt.side_effect = [
                "http://localhorst:2357",
                "login",
                "http://localhorst:2357/auth/login",
                "bibo",
                "******",
                "bibo",
                "X-Auth-Token",
            ]
            # Simulate response to typer.confirm()
            mock_confirm.side_effect = [
                True,
            ]
            mock_prompt.assert_not_called()
            mock_confirm.assert_not_called()
            mock_login.assert_not_called()
            actual_config_path = configure_client_with_prompt()
            self.assert_is_default_config_path(actual_config_path)
            config = get_config(None)
            self.assertEqual(
                ClientConfig(
                    auth_type="login",
                    api_url="http://localhorst:2357",
                    auth_url="http://localhorst:2357/auth/login",
                    username="bibo",
                    password=expected_password,
                    token="dummy-token",
                    use_bearer=True,
                ),
                config,
            )

    @patch("typer.prompt")
    def test_using_custom_config_path(self, mock_prompt: MagicMock):
        # Simulate sequential responses to typer.prompt()
        mock_prompt.side_effect = ["http://localhost:9090", "none"]
        custom_config_path = Path("my-config.cfg")
        try:
            actual_config_path = configure_client_with_prompt(
                config_path=custom_config_path
            )
            self.assertEqual(2, mock_prompt.call_count)
            self.assertEqual(custom_config_path, actual_config_path)
            self.assertTrue(custom_config_path.exists())
            config = get_config(custom_config_path)
            self.assertEqual(
                ClientConfig(api_url="http://localhost:9090", auth_type="none"),
                config,
            )
        finally:
            if custom_config_path.exists():
                os.remove(custom_config_path)
