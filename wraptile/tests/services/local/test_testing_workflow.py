#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import IsolatedAsyncioTestCase, TestCase

from gavicore.models import (
    InputDescription,
    JobResults,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from procodile import Job, Process
from wraptile.services.local.testing_workflow import service as testing_service


class TestingWorkflowsTest(TestCase):
    def setUp(self):
        self.registry = testing_service.process_registry

    def test_run_sleep_a_while(self):
        process = self.registry.get("first_workflow")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest(inputs={"id": "hello"}))
        job_results = job.run()
        self.assertIsInstance(job_results, JobResults)


class TestingServiceTest(IsolatedAsyncioTestCase):
    async def test_get_processes(self):
        class MockRequest:
            # noinspection PyMethodMayBeStatic
            def url_for(self, name, **_params):
                return f"https://api.com/{name}"

        process_list = await testing_service.get_processes(request=MockRequest())
        self.assertIsInstance(process_list, ProcessList)
        process_dict = {v.id: v for v in process_list.processes}
        self.assertEqual(
            {
                "first_workflow",
            },
            set(process_dict.keys()),
        )

    async def test_get_process(self):
        process = await testing_service.get_process(process_id="first_workflow")
        self.assertIsInstance(process, ProcessDescription)
        self.assertIsInstance(process.inputs, dict)

        id = process.inputs.get("id")
        self.assertIsInstance(id, InputDescription)
        self.assertEqual("main input", id.title)
        self.assertEqual(
            {"default": "hithere", "type": "string"},
            id.schema_.model_dump(
                mode="json",
                exclude_defaults=True,
                exclude_none=True,
            ),
        )
