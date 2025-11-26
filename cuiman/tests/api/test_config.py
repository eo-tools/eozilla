#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from cuiman.api.auth import AuthType
from cuiman.api.config import ClientConfig
from cuiman.api.defaults import DEFAULT_CONFIG_PATH


class ClientConfigTest(TestCase):
    def setUp(self):
        self.saved_environ = {
            k: v for k, v in os.environ.items() if k.startswith("EOZILLA_")
        }
        for k in self.saved_environ.keys():
            del os.environ[k]

    def tearDown(self):
        self.saved_environ = {
            k: v for k, v in os.environ.items() if k.startswith("EOZILLA_")
        }
        for k, v in self.saved_environ.items():
            os.environ[k] = v

    def test_ctor(self):
        config = ClientConfig()
        self.assertEqual(None, config.api_url)
        self.assertEqual(None, config.auth_url)
        self.assertEqual(None, config.auth_type)

    def test_create_empty(self):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config = ClientConfig.create(config_path=config_path)
            self.assertIsInstance(config, ClientConfig)
            self.assertEqual("http://127.0.0.1:8008", config.api_url)
            self.assertEqual(None, config.auth_type)

    def test_create_from_env(self):
        os.environ.update(
            dict(
                EOZILLA_API_URL="https://eozilla.pippo.api",
                EOZILLA_AUTH_TYPE="none",
            )
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config = ClientConfig.create(config_path=config_path)
            self.assertIsInstance(config, ClientConfig)
            self.assertEqual("https://eozilla.pippo.api", config.api_url)
            self.assertEqual("none", config.auth_type)

    def test_create_from_env_with_auth(self):
        os.environ.update(
            dict(
                EOZILLA_API_URL="https://eozilla.pippo.api",
                EOZILLA_AUTH_TYPE="login",
                EOZILLA_AUTH_URL="https://eozilla.pippo.api/auth/login",
                EOZILLA_USERNAME="pippo",
                EOZILLA_PASSWORD="poppi",
                EOZILLA_TOKEN="0f8915a4",
            )
        )
        config = ClientConfig()
        self.assertIsInstance(config, ClientConfig)
        self.assertEqual("https://eozilla.pippo.api", config.api_url)
        self.assertEqual("login", config.auth_type)
        self.assertEqual("https://eozilla.pippo.api/auth/login", config.auth_url)
        self.assertEqual("pippo", config.username)
        self.assertEqual("poppi", config.password)
        self.assertEqual("0f8915a4", config.token)

    def test_create_from_file(self):
        config = ClientConfig(
            api_url="https://eozilla.pippo.api",
        )
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config.write(config_path=config_path)
            config = ClientConfig.create(config_path=config_path)
            self.assertEqual("https://eozilla.pippo.api", config.api_url)
            self.assertEqual(None, config.auth_type)

    def test_create_from_env_and_file(self):
        os.environ.update(
            dict(
                # Should take precedence!
                EOZILLA_API_URL="https://eozilla.test.api",
            )
        )
        config = ClientConfig(api_url="https://eozilla.pippo.api")
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            config_path = Path(tmp_dir_name) / "config"
            config.write(config_path=config_path)
            config = ClientConfig.create(config_path=config_path)
            self.assertEqual("https://eozilla.test.api", config.api_url)
            self.assertEqual(None, config.auth_type)

    def test_normalize_config_path(self):
        path = Path("i/am/a/path")
        self.assertIs(path, ClientConfig.normalize_config_path(path))
        self.assertEqual(path, ClientConfig.normalize_config_path("i/am/a/path"))
        self.assertEqual(DEFAULT_CONFIG_PATH, ClientConfig.normalize_config_path(""))

    def test_get_set_get_default(self):
        d1 = ClientConfig.get_default()
        self.assertEqual({"api_url": "http://127.0.0.1:8008"}, d1.to_dict())
        d2 = ClientConfig.set_default(
            ClientConfig(
                api_url="http://pippo.service.org",
            )
        )
        self.assertEqual(d1, d2)
        self.assertEqual(
            dict(
                api_url="http://pippo.service.org",
            ),
            ClientConfig.get_default().to_dict(),
        )
