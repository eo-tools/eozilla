#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Optional
from unittest import TestCase

import pytest

from s2gos_common.models import (
    JobInfo,
    JobList,
    JobResults,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from s2gos_common.util.testing import set_env_cm
from s2gos_server.constants import ENV_VAR_SERVICE
from s2gos_server.exceptions import ServiceConfigException
from s2gos_server.services.base import ServiceBase


class MyService(ServiceBase):
    def __init__(self):
        super().__init__("Test Service")
        self.threads: Optional[bool] = None
        self.workers: Optional[int] = None

    def configure(self, threads: Optional[bool] = None, workers: Optional[int] = None):
        self.threads = threads
        self.workers = workers

    async def get_processes(self, *args, **kwargs) -> ProcessList:
        raise NotImplementedError

    async def get_process(self, process_id: str, *args, **kwargs) -> ProcessDescription:
        raise NotImplementedError

    async def execute_process(
        self, process_id: str, process_request: ProcessRequest, *args, **kwargs
    ) -> JobInfo:
        raise NotImplementedError

    async def get_jobs(self, *args, **kwargs) -> JobList:
        raise NotImplementedError

    async def get_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        raise NotImplementedError

    async def dismiss_job(self, job_id: str, *args, **kwargs) -> JobInfo:
        raise NotImplementedError

    async def get_job_results(self, job_id: str, *args, **kwargs) -> JobResults:
        raise NotImplementedError


service = MyService()


class ServiceBaseTest(TestCase):
    def test_load_without_options(self):
        service_spec = "tests.services.base.test_service_base:service"
        with set_env_cm(**{ENV_VAR_SERVICE: service_spec}):
            s = ServiceBase.load()
        self.assertIsInstance(s, MyService)
        self.assertEqual(None, s.threads)
        self.assertEqual(None, s.workers)

    def test_load_with_options(self):
        service_spec = (
            "tests.services.base.test_service_base:service --threads --workers=4"
        )
        with set_env_cm(**{ENV_VAR_SERVICE: service_spec}):
            s = ServiceBase.load()
        self.assertIsInstance(s, MyService)
        self.assertEqual(True, s.threads)
        self.assertEqual(4, s.workers)

    def test_load_with_no_option(self):
        service_spec = (
            "tests.services.base.test_service_base:service --no-threads --workers=2"
        )
        with set_env_cm(**{ENV_VAR_SERVICE: service_spec}):
            s = ServiceBase.load()
        self.assertIsInstance(s, MyService)
        self.assertEqual(False, s.threads)
        self.assertEqual(2, s.workers)

    def test_load_env_var_not_set(self):
        self.assert_fails_with_config_exception(
            None, r"Service not specified\. The service must be passed in the form"
        )

    def test_load_env_var_empty(self):
        self.assert_fails_with_config_exception(
            "", r"Service not specified\. The service must be passed in the form"
        )

    def test_load_env_var_with_invalid_service_spec(self):
        self.assert_fails_with_config_exception(
            "hello.service",
            r"The service reference must be passed in the form "
            r"'path\.to\.module\:service', but got 'hello\.service'\.",
        )

    def test_load_env_var_with_invalid_service_module(self):
        self.assert_fails_with_config_exception(
            "hel.lo:service",
            r"Cannot import module 'hel.lo'\.",
        )

    def test_load_env_var_with_invalid_service_attrib(self):
        self.assert_fails_with_config_exception(
            "tests.services.base.test_service_base:servize",
            r"Module 'tests\.services\.base\.test_service_base' "
            r"has no attribute 'servize'\.",
        )

    def test_load_env_var_with_invalid_service_type(self):
        self.assert_fails_with_config_exception(
            "tests.services.base.test_service_base:MyService",
            r"The reference 'tests\.services\.base\.test_service_base:MyService' "
            r"should refer to a service of type ServiceBase, but got type ABCMeta\.",
        )

    def test_load_env_var_with_invalid_opt(self):
        self.assert_fails_with_config_exception(
            "module:attr -pippo",
            r"Service options must have the form '\-\-key\[=value\]', "
            r"but got '-pippo'\.",
        )

    def test_load_env_var_with_invalid_opt_ident(self):
        self.assert_fails_with_config_exception(
            "module:attr --12=13",
            r"Service options must have the form '--key\[=value\]', "
            r"but got '12' as key, which is not an identifier\.",
        )

    # noinspection PyMethodMayBeStatic
    def assert_fails_with_config_exception(self, value: str | None, match: str):
        with set_env_cm(**{ENV_VAR_SERVICE: value}):
            with pytest.raises(ServiceConfigException, match=match):
                ServiceBase.load()
