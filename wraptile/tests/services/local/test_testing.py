#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch
from urllib.parse import urljoin

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

    def test_run_simulate_stac_item(self):
        with TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir) / "result with spaces"
            process = self.registry.get("simulate_stac_item")
            self.assertIsInstance(process, Process)
            job = Job.create(
                process, ProcessRequest(inputs={"output_dir": str(directory)})
            )
            results = job.run()

            self.assertEqual(JobStatus.successful, job.job_info.status)
            self.assertIsInstance(results, JobResults)
            self.assertEqual({"result", "report"}, set(results.root))
            item = results.root["result"]
            self.assertEqual(
                json.loads((directory / "item.json").read_text(encoding="utf-8")),
                item,
            )
            self._assert_stac_item(item, "2026-09-01")
            self.assertEqual("products", item["assets"]["products"]["href"])
            self.assertNotIn("type", item["assets"]["products"])
            self.assertNotIn("roles", item["assets"]["report"])
            self.assertNotIn("title", item["assets"]["report"])
            self.assertEqual(
                (directory / "products" / "tables" / "observations.csv").as_uri(),
                urljoin(item["links"][0]["href"], item["assets"]["data"]["href"]),
            )
            report = results.root["report"]
            self.assertIsInstance(report, Link)
            self.assertEqual("text/plain", report.type)
            self.assertEqual(
                (directory / "products" / "reports" / "summary.txt").as_uri(),
                report.href,
            )
            self.assertEqual(
                "Vegetation observations for 2026-09-01\n",
                (directory / "products" / "reports" / "summary.txt").read_text(
                    encoding="utf-8"
                ),
            )
            restored = JobResults.model_validate_json(results.model_dump_json())
            self.assertEqual(results, restored)

    def test_run_simulate_stac_item_collection(self):
        with TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir) / "result with spaces"
            process = self.registry.get("simulate_stac_item_collection")
            self.assertIsInstance(process, Process)
            job = Job.create(
                process, ProcessRequest(inputs={"output_dir": str(directory)})
            )
            results = job.run()

            self.assertEqual(JobStatus.successful, job.job_info.status)
            self.assertIsInstance(results, JobResults)
            self.assertEqual({"result"}, set(results.root))
            link = results.root["result"]
            self.assertIsInstance(link, Link)
            self.assertEqual((directory / "items.json").as_uri(), link.href)
            self.assertEqual("application/geo+json", link.type)
            collection = json.loads(
                (directory / "items.json").read_text(encoding="utf-8")
            )
            self.assertEqual("FeatureCollection", collection["type"])
            self.assertNotIn("stac_version", collection)
            self.assertEqual(2, len(collection["features"]))
            self.assertEqual(link.href, collection["links"][0]["href"])
            for item, date in zip(
                collection["features"], ["2026-09-01", "2026-09-02"], strict=True
            ):
                self._assert_stac_item(item, date)
                self.assertEqual({"data", "report", "products"}, set(item["assets"]))
                standalone = json.loads(
                    (directory / date / "item.json").read_text(encoding="utf-8")
                )
                for key, asset in item["assets"].items():
                    self.assertEqual(
                        f"{date}/{standalone['assets'][key]['href']}", asset["href"]
                    )
                    self.assertEqual(
                        (directory / date / standalone["assets"][key]["href"]).as_uri(),
                        urljoin(link.href, asset["href"]),
                    )
                self.assertEqual(
                    f"date,ndvi\n{date},0.75\n",
                    (
                        directory / date / "products" / "tables" / "observations.csv"
                    ).read_text(encoding="utf-8"),
                )
            restored = JobResults.model_validate_json(results.model_dump_json())
            self.assertEqual(results, restored)

    def test_stac_process_output_schemas(self):
        item_schema = (
            self.registry.get("simulate_stac_item")
            .description.outputs["result"]
            .schema_
        )
        self.assertEqual(
            "https://schemas.stacspec.org/v1.1.0/item-spec/json-schema/item.json",
            item_schema.ref,
        )
        collection_schema = (
            self.registry.get("simulate_stac_item_collection")
            .description.outputs["result"]
            .schema_
        )
        schema = collection_schema.model_dump(mode="json", by_alias=True)
        self.assertEqual(["FeatureCollection"], schema["properties"]["type"]["enum"])
        self.assertEqual(
            item_schema.ref, schema["properties"]["features"]["items"]["$ref"]
        )

    def _assert_stac_item(self, item, date):
        self.assertEqual("Feature", item["type"])
        self.assertEqual("1.1.0", item["stac_version"])
        self.assertEqual(f"ndvi-{date}", item["id"])
        self.assertIsNone(item["geometry"])
        self.assertEqual(f"{date}T00:00:00Z", item["properties"]["datetime"])
        self.assertEqual("self", item["links"][0]["rel"])
        self.assertEqual("text/csv", item["assets"]["data"]["type"])
        self.assertEqual("NDVI observations", item["assets"]["data"]["title"])
        self.assertEqual(["data"], item["assets"]["data"]["roles"])

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
                "simulate_stac_item",
                "simulate_stac_item_collection",
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
