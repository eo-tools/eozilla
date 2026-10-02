#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from unittest import TestCase

from gavicore.service.core import Service
from gavicore.service.dru import DruService

from .test_core import REQUIRED_METHODS as REQUIRED_SERVICE_METHODS

REQUIRED_DRU_METHODS = {
    "deploy_process",
    "replace_process",
    "undeploy_process",
    "get_formal_description",
}

REQUIRED_DRU_METHODS |= REQUIRED_SERVICE_METHODS


class DRUServiceTest(TestCase):
    def test_extends_core_interface(self):
        self.assertTrue(issubclass(DruService, Service))

    def test_methods(self):
        all_method_names = set(
            name for name, obj in inspect.getmembers(DruService, inspect.isfunction)
        )
        self.assertSetEqual(REQUIRED_DRU_METHODS, set(all_method_names))
