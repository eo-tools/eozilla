#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from unittest import TestCase

from s2gos_common.service import Service

REQUIRED_METHODS = {
    "dismiss_job",
    "execute_process",
    "get_capabilities",
    "get_conformance",
    "get_job_results",
    "get_process",
    "get_processes",
    "get_job",
    "get_jobs",
}


class ServiceTest(TestCase):
    def test_methods(self):
        all_method_names = set(
            name for name, obj in inspect.getmembers(Service, inspect.isfunction)
        )
        self.assertSetEqual(REQUIRED_METHODS, set(all_method_names))
