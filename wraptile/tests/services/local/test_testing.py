#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

import wraptile.services.local.testing as testing_module
from gavicore.models import (
    InputDescription,
    JobResults,
    JobStatus,
    Link,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from procodile import Job, Process
from wraptile.services.local.testing import SceneSpec
from wraptile.services.local.testing import service as testing_service


class TestingFunctionsTest(TestCase):
    def setUp(self):
        self.registry = testing_service.process_registry

    def test_run_sleep_a_while(self):
        process = self.registry.get("sleep_a_while")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest(inputs={"duration": 0.05}))
        job_results = job.run()
        self.assertIsInstance(job_results, JobResults)

    def test_run_sleep_a_while_can_fail(self):
        process = self.registry.get("sleep_a_while")
        self.assertIsInstance(process, Process)
        job = Job.create(
            process,
            ProcessRequest(inputs={"duration": 0.0, "fail": True}),
        )

        self.assertIsNone(job.run())
        self.assertEqual(JobStatus.failed, job.job_info.status)
        self.assertEqual("Woke up too early", job.job_info.message)

    def test_run_primes_between(self):
        process = self.registry.get("primes_between")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest())
        job_results = job.run()
        self.assertIsInstance(job_results, JobResults)

    def test_run_primes_between_rejects_invalid_range(self):
        process = self.registry.get("primes_between")
        self.assertIsInstance(process, Process)
        job = Job.create(
            process,
            ProcessRequest(inputs={"min_val": 10, "max_val": 10}),
        )

        self.assertIsNone(job.run())
        self.assertEqual(JobStatus.failed, job.job_info.status)
        self.assertEqual(
            "max_val must be greater 1 and greater min_val",
            job.job_info.message,
        )

    def test_run_return_base_model(self):
        process = self.registry.get("return_base_model")
        self.assertIsInstance(process, Process)
        job = Job.create(
            process,
            ProcessRequest(inputs={"scene_spec": SceneSpec(threshold=0.2, factor=2)}),
        )
        job_results = job.run()
        self.assertIsInstance(job_results, JobResults)

    def test_run_simulate_scene(self):
        inputs = {
            "var_names": "a, b",
            "bbox": [-10, 30, 5, 45],
            "resolution": 1,
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
            "periodicity": 1,
            "output_path": None,
        }

        process = self.registry.get("simulate_scene")
        self.assertIsInstance(process, Process)
        job = Job.create(process, ProcessRequest(inputs=inputs))
        job_results = job.run()
        self.assertIsInstance(job_results, JobResults)
        json_dict = job_results.model_dump(mode="json")
        self.assertIsInstance(json_dict, dict)
        self.assertIsInstance(json_dict.get("return_value"), dict)
        link = Link(**json_dict.get("return_value"))
        self.assertIsInstance(link.href, str)
        self.assertTrue(link.href.startswith("memory://"))
        self.assertTrue(link.href.endswith(".zarr"))
        try:
            import xarray as xr

            ds = xr.open_dataset(link.href)
            self.assertIsInstance(ds, xr.Dataset)
            self.assertEqual({"time": 2, "lat": 15, "lon": 15}, ds.sizes)
            self.assertEqual({"time", "lat", "lon"}, set(ds.coords.keys()))
            self.assertEqual({"a", "b"}, set(ds.data_vars.keys()))
        except ImportError:
            pass

    def test_run_simulate_scene_with_file_output_path(self):
        with TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/datacube.zarr"
            inputs = {
                "var_names": "a",
                "bbox": [-10, 30, -8, 32],
                "resolution": 1,
                "start_date": "2025-01-01",
                "end_date": "2025-01-02",
                "periodicity": 1,
                "output_path": output_path,
            }

            process = self.registry.get("simulate_scene")
            self.assertIsInstance(process, Process)
            job = Job.create(process, ProcessRequest(inputs=inputs))
            job_results = job.run()

            self.assertIsInstance(job_results, JobResults)
            link = Link(**job_results.model_dump(mode="json")["return_value"])
            self.assertTrue(link.href.startswith("file:///"))
            self.assertTrue(link.href.endswith("/datacube.zarr"))

    def test_run_processor(self):
        process = self.registry.get("218")
        self.assertIsInstance(process, Process)
        job = Job.create(
            process,
            ProcessRequest(
                inputs={
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31",
                    "geometry": "POINT (1 2)",
                    "indicator_name": "NDVI",
                    "site_extend": "POINT (3 4)",
                }
            ),
        )

        with patch.object(testing_module.time, "sleep", return_value=None):
            job_results = job.run()

        self.assertIsInstance(job_results, JobResults)
        self.assertEqual(JobStatus.successful, job.job_info.status)
        self.assertEqual("Ended processing", job.job_info.message)
        self.assertEqual(
            {
                "return_value": {
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31",
                    "geometry": "POINT (1 2)",
                    "indicator_name": "NDVI",
                    "site_extend": "POINT (3 4)",
                }
            },
            job_results.model_dump(mode="json"),
        )


class TestingWorkflowsTest(TestCase):
    def setUp(self):
        self.registry = testing_service.process_registry

    def test_test_workflow(self):
        process = self.registry.get("process_pipeline")
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
                "primes_between",
                "return_base_model",
                "simulate_scene",
                "sleep_a_while",
                "process_pipeline",
                "218",
            },
            set(process_dict.keys()),
        )

    async def test_get_process(self):
        process = await testing_service.get_process(process_id="simulate_scene")
        self.assertIsInstance(process, ProcessDescription)
        self.assertIsInstance(process.inputs, dict)

        bbox_input = process.inputs.get("bbox")
        self.assertIsInstance(bbox_input, InputDescription)
        self.assertEqual("Bounding box", bbox_input.title)
        self.assertEqual(
            "Bounding box in geographical coordinates.", bbox_input.description
        )
        self.assertEqual(
            {
                "type": "array",
                "default": [-180, -90, 180, 90],
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 4,
                "x-ui-widget": "map",
            },
            bbox_input.schema_.model_dump(
                mode="json",
                exclude_defaults=True,
                exclude_none=True,
            ),
        )

        start_date_input = process.inputs.get("start_date")
        self.assertIsInstance(start_date_input, InputDescription)
        self.assertEqual("Start date", start_date_input.title)
        self.assertEqual(None, start_date_input.description)
        self.assertEqual(
            {
                "type": "string",
                "format": "date",
                "default": "2025-01-01",
            },
            start_date_input.schema_.model_dump(
                mode="json",
                exclude_defaults=True,
                exclude_none=True,
            ),
        )
