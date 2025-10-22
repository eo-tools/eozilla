#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from fastapi import FastAPI

from s2gos_server.main import app


class MainTest(TestCase):
    def test_service_provider_init_ok(self):
        self.assertIsInstance(app, FastAPI)
