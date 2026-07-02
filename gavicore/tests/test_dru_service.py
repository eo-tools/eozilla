#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from unittest import TestCase

from gavicore.dru_service import DRUService

from .test_service import REQUIRED_METHODS as REQUIRED_SERVICE_METHODS

REQUIRED_DRU_METHODS = {
    "deploy_process",
    "replace_process",
    "undeploy_process",
    "get_formal_description",
}

REQUIRED_DRU_METHODS |= REQUIRED_SERVICE_METHODS


class DRUServiceTest(TestCase):
    def test_methods(self):
        all_method_names = set(
            name for name, obj in inspect.getmembers(DRUService, inspect.isfunction)
        )
        self.assertSetEqual(REQUIRED_DRU_METHODS, set(all_method_names))
