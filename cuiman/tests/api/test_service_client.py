#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import IsolatedAsyncioTestCase, TestCase

from cuiman.api.jobs import JobOptions
from cuiman.api.service_client import generate_service_client_modules
from gavicore.models import DataType, InputDescription, ProcessDescription, Schema


def mk_process_description() -> ProcessDescription:
    return ProcessDescription(
        id="simulate-scene",
        version="1.0.0",
        title="Simulate scene",
        inputs={
            "bbox": InputDescription(
                title="Bounding box",
                schema=Schema(type=DataType.array, items=Schema(type=DataType.number)),
            ),
            "class": InputDescription(
                title="Class name",
                schema=Schema(type=DataType.string),
            ),
            "job_options": InputDescription(
                minOccurs=0,
                title="Server-side job options",
                schema=Schema(type=DataType.object),
            ),
        },
    )


class GenerateServiceClientModulesTest(TestCase):
    def test_sync_client_class_executes_generated_method(self):
        generated = generate_service_client_modules("s2gos", [mk_process_description()])
        self.assertEqual("s2gos_sync", generated.sync_module_name)
        self.assertEqual("S2gosClient", generated.sync_class_name)
        namespace: dict[str, object] = {}
        exec(generated.sync_code, namespace)  # noqa: S102
        calls = []

        def fake_helper(self, process_id, request, *, job_options=None):
            calls.append((self, process_id, request, job_options))
            return "opened"

        namespace["execute_and_open_result"] = fake_helper
        client_cls = namespace["S2gosClient"]
        client = client_cls(api_url="https://acme.ogc.org/api")
        options = JobOptions(timeout=1)
        result = client.simulate_scene(
            bbox=[1.0, 2.0, 3.0, 4.0],
            class_="snow",
            job_options_=None,
            job_options=options,
        )
        self.assertEqual("opened", result)
        _, process_id, request, job_options = calls[0]
        self.assertEqual("simulate-scene", process_id)
        self.assertEqual(
            {"bbox": [1.0, 2.0, 3.0, 4.0], "class": "snow"},
            request.inputs,
        )
        self.assertIs(options, job_options)


class GenerateAsyncServiceClientModulesTest(IsolatedAsyncioTestCase):
    async def test_async_client_class_executes_generated_method(self):
        generated = generate_service_client_modules("s2gos", [mk_process_description()])
        self.assertEqual("s2gos_async", generated.async_module_name)
        self.assertEqual("S2gosAsyncClient", generated.async_class_name)
        namespace: dict[str, object] = {}
        exec(generated.async_code, namespace)  # noqa: S102
        calls = []

        async def fake_helper(self, process_id, request, *, job_options=None):
            calls.append((self, process_id, request, job_options))
            return "opened"

        namespace["async_execute_and_open_result"] = fake_helper
        client_cls = namespace["S2gosAsyncClient"]
        client = client_cls(api_url="https://acme.ogc.org/api")
        result = await client.simulate_scene(
            bbox=[1.0, 2.0, 3.0, 4.0],
            class_="snow",
        )
        self.assertEqual("opened", result)
        _, process_id, request, job_options = calls[0]
        self.assertEqual("simulate-scene", process_id)
        self.assertEqual(
            {"bbox": [1.0, 2.0, 3.0, 4.0], "class": "snow"},
            request.inputs,
        )
        self.assertIsNone(job_options)
