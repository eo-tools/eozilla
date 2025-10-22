#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from s2gos_common.util.testing import set_env_cm
from s2gos_server.exceptions import ServiceConfigException
from s2gos_server.provider import ServiceProvider, get_service
from s2gos_server.services.local import LocalService
from s2gos_server.services.local.testing import service as test_service


class ServiceProviderTest(TestCase):
    def setUp(self):
        ServiceProvider._service = None

    def test_set_directly(self):
        service = LocalService(title="Test service")
        ServiceProvider.set_instance(service)
        self.assertIs(service, ServiceProvider.get_instance())
        self.assertIs(service, get_service())

    # noinspection PyMethodMayBeStatic
    def test_set_from_env_var(self):
        with set_env_cm(S2GOS_SERVICE="s2gos_server.services.local.testing:service"):
            self.assertIs(test_service, ServiceProvider.get_instance())
            self.assertIs(test_service, get_service())

    # noinspection PyMethodMayBeStatic
    def test_not_set(self):
        with set_env_cm(S2GOS_SERVICE=None):
            with pytest.raises(
                ServiceConfigException,
                match=(
                    "Service not specified. "
                    "The service must be passed in the form "
                    "'path.to.module:service'"
                ),
            ):
                ServiceProvider.get_instance()
