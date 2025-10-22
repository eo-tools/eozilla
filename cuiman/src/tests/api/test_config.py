#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from s2gos_client.api.config import ClientConfig
from s2gos_client.api.defaults import DEFAULT_CONFIG_PATH


class ClientConfigTest(TestCase):
    def setUp(self):
        self.saved_environ = {
            k: v for k, v in os.environ.items() if k.startswith("S2GOS_")
        }
        for k in self.saved_environ.keys():
            del os.environ[k]

    def tearDown(self):
        self.saved_environ = {
            k: v for k, v in os.environ.items() if k.startswith("S2GOS_")
        }
        for k, v in self.saved_environ.items():
            os.environ[k] = v

    def test_ctor(self):
        config = ClientConfig()
        self.assertEqual(None, config.user_name)
        self.assertEqual(None, config.access_token)
        self.assertEqual(None, config.server_url)

    def test_create_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config = ClientConfig.create(config_path=config_path)
            self.assertIsInstance(config, ClientConfig)
            self.assertEqual("http://127.0.0.1:8008", config.server_url)
            self.assertEqual(None, config.user_name)
            self.assertEqual(None, config.access_token)

    def test_create_from_env(self):
        os.environ.update(
            dict(
                S2GOS_SERVER_URL="https://s2gos.test.api",
                S2GOS_USER_NAME="pippo",
                S2GOS_ACCESS_TOKEN="0f8915a4",
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config = ClientConfig.create(config_path=config_path)
            self.assertIsInstance(config, ClientConfig)
            self.assertEqual("https://s2gos.test.api", config.server_url)
            self.assertEqual("pippo", config.user_name)
            self.assertEqual("0f8915a4", config.access_token)

    def test_create_from_file(self):
        config = ClientConfig(
            server_url="https://s2gos.test2.api", user_name="bibo", access_token="981b"
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config.write(config_path=config_path)
            config = ClientConfig.create(config_path=config_path)
            self.assertEqual("https://s2gos.test2.api", config.server_url)
            self.assertEqual("bibo", config.user_name)
            self.assertEqual("981b", config.access_token)

    def test_create_from_file_and_env(self):
        os.environ.update(
            dict(
                S2GOS_SERVER_URL="https://s2gos.test.api",
                S2GOS_USER_NAME="pippo",
                S2GOS_ACCESS_TOKEN="0f8915a4",
            )
        )
        config = ClientConfig(server_url="https://s2gos.test2.api", user_name="bibi")
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config.write(config_path=config_path)
            config = ClientConfig.create(config_path=config_path)
            self.assertEqual("https://s2gos.test.api", config.server_url)
            self.assertEqual("pippo", config.user_name)
            self.assertEqual("0f8915a4", config.access_token)

    def test_normalize_config_path(self):
        path = Path("i/am/a/path")
        self.assertIs(path, ClientConfig.normalize_config_path(path))
        self.assertEqual(path, ClientConfig.normalize_config_path("i/am/a/path"))
        self.assertEqual(DEFAULT_CONFIG_PATH, ClientConfig.normalize_config_path(""))
