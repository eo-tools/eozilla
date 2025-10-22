#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import click
import pytest

from s2gos_client import ClientConfig
from s2gos_client.api.defaults import DEFAULT_CONFIG_PATH
from s2gos_client.cli.config import configure_client, get_config
from s2gos_common.util.testing import set_env, set_env_cm

DEFAULT_CONFIG_BACKUP_PATH = DEFAULT_CONFIG_PATH.parent / (
    str(DEFAULT_CONFIG_PATH.name) + ".backup"
)


class ReadConfigTest(unittest.TestCase):
    def setUp(self):
        self.restore_env = set_env(
            **{k: None for k, v in os.environ.items() if k.startswith("S2GOS_")}
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

    @patch("typer.prompt")
    def test_configure_client_default(self, mock_prompt):
        mock_prompt.side_effect = ["bibo", "ip245", "http://localhorst:9999"]
        actual_config_path = configure_client()
        self.assertEqual(DEFAULT_CONFIG_PATH, actual_config_path)
        self.assertTrue(DEFAULT_CONFIG_PATH.exists())
        config = get_config(None)
        self.assertEqual(
            ClientConfig(
                user_name="bibo",
                access_token="ip245",
                server_url="http://localhorst:9999",
            ),
            config,
        )

    @patch("typer.prompt")
    def test_configure_client_custom(self, mock_prompt):
        # Simulate sequential responses to typer.prompt
        mock_prompt.side_effect = ["bert", "s3cr3t", "http://localhorst:9090"]
        custom_config_path = Path("test.cfg")
        try:
            actual_config_path = configure_client(config_path=custom_config_path)
            self.assertEqual(custom_config_path, actual_config_path)
            self.assertTrue(custom_config_path.exists())
            config = get_config(custom_config_path)
            self.assertEqual(
                ClientConfig(
                    user_name="bert",
                    access_token="s3cr3t",
                    server_url="http://localhorst:9090",
                ),
                config,
            )
        finally:
            if custom_config_path.exists():
                os.remove(custom_config_path)

    @patch("typer.prompt")
    def test_configure_client_use_defaults(self, mock_prompt):
        # Simulate sequential responses to typer.prompt
        with set_env_cm(
            S2GOS_USER_NAME="bibo",
            S2GOS_ACCESS_TOKEN="9823hc",
            S2GOS_SERVER_URL="http://localhorst:2357",
        ):
            mock_prompt.side_effect = ["bibo", "*****", "http://localhorst:2357"]
            custom_config_path = Path("test.cfg")
            try:
                actual_config_path = configure_client(config_path=custom_config_path)
                self.assertEqual(custom_config_path, actual_config_path)
                self.assertTrue(custom_config_path.exists())
                config = get_config(custom_config_path)
                self.assertEqual(
                    ClientConfig(
                        user_name="bibo",
                        access_token="9823hc",
                        server_url="http://localhorst:2357",
                    ),
                    config,
                )
            finally:
                if custom_config_path.exists():
                    os.remove(custom_config_path)
