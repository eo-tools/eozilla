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
from cuiman.cli.config import configure_client, get_config
from gavicore.util.testing import set_env, set_env_cm

DEFAULT_CONFIG_BACKUP_PATH = DEFAULT_CONFIG_PATH.parent / (
    str(DEFAULT_CONFIG_PATH.name) + ".backup"
)


class ReadConfigTest(unittest.TestCase):
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

    @patch("cuiman.cli.config.login", return_value="dummy-token")
    @patch("typer.prompt")
    def test_configure_client_default(
        self, mock_prompt: MagicMock, mock_login: MagicMock
    ):
        mock_prompt.side_effect = [
            "http://localhorst:9999",
            "login",
            "http://localhorst:9999/signon",
            "bibo",
            "1234",
        ]
        actual_config_path = configure_client()
        mock_login.assert_called_once()
        self.assertEqual(5, mock_prompt.call_count)
        self.assertEqual(DEFAULT_CONFIG_PATH, actual_config_path)
        self.assertTrue(DEFAULT_CONFIG_PATH.exists())
        config = get_config(None)
        self.assertEqual(
            ClientConfig(
                api_url="http://localhorst:9999",
                auth_type="login",
                auth_url="http://localhorst:9999/signon",
                username="bibo",
                password="1234",
                token="dummy-token",
            ),
            config,
        )

    @patch("typer.prompt")
    def test_configure_client_custom(self, mock_prompt: MagicMock):
        # Simulate sequential responses to typer.prompt
        mock_prompt.side_effect = ["http://localhost:9090", "none"]
        custom_config_path = Path("test.cfg")
        try:
            actual_config_path = configure_client(config_path=custom_config_path)
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

    @patch("cuiman.cli.config.login", return_value="dummy-token")
    @patch("typer.prompt")
    def test_configure_client_use_defaults(
        self, mock_prompt: MagicMock, mock_login: MagicMock
    ):
        # Simulate sequential responses to typer.prompt
        with set_env_cm(
            EOZILLA_API_URL="http://localhorst:2357",
            EOZILLA_AUTH_TYPE="login",
            EOZILLA_AUTH_URL="http://localhorst:2357/auth/login",
            EOZILLA_USERNAME="bibo",
            EOZILLA_PASSWORD="9823hc",
        ):
            mock_prompt.side_effect = [
                "http://localhorst:2357",
                "login",
                "http://localhorst:2357/auth/login",
                "bibo",
                "******",
            ]
            custom_config_path = Path("test.cfg")
            mock_prompt.assert_not_called()
            mock_login.assert_not_called()
            try:
                actual_config_path = configure_client(config_path=custom_config_path)
                self.assertEqual(custom_config_path, actual_config_path)
                self.assertTrue(custom_config_path.exists())
                config = get_config(custom_config_path)
                self.assertEqual(
                    ClientConfig(
                        auth_type="login",
                        api_url="http://localhorst:2357",
                        username="bibo",
                        password="9823hc",
                        token="dummy-token",
                    ),
                    config,
                )
            finally:
                if custom_config_path.exists():
                    os.remove(custom_config_path)
