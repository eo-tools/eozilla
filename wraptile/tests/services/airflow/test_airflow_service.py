#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import unittest
import warnings
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, patch

import fastapi
import requests

from gavicore.models import (
    Capabilities,
    ConformanceDeclaration,
    DataType,
    ProcessDescription,
    ProcessList,
)
from gavicore.util.testing import set_env
from wraptile.main import app
from wraptile.provider import ServiceProvider, get_service
from wraptile.services.airflow import DEFAULT_AIRFLOW_BASE_URL, AirflowService


class ParamToInputDescriptionTest(TestCase):
    def test_string_param(self):
        result = AirflowService._param_to_input_description(
            "scene_name",
            {
                "value": "scene",
                "description": "Scene id name.",
                "schema": {"type": "string", "title": "Scene Name"},
            },
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Scene Name")
        self.assertEqual(result.description, "Scene id name.")
        self.assertEqual(result.schema_.type, DataType.string)
        self.assertEqual(result.schema_.default, "scene")
        self.assertEqual(result.minOccurs, 1)

    def test_number_param(self):
        result = AirflowService._param_to_input_description(
            "target_lat",
            {
                "value": 41.808,
                "description": "Target's center latitude.",
                "schema": {"type": "number", "title": "Target Lat"},
            },
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_.type, DataType.number)
        self.assertEqual(result.schema_.default, 41.808)
        self.assertEqual(result.minOccurs, 1)

    def test_integer_param(self):
        result = AirflowService._param_to_input_description(
            "spp",
            {
                "value": 8,
                "description": "Number of Monte Carlo samples.",
                "schema": {"type": "integer", "title": "Spp"},
            },
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_.type, DataType.integer)
        self.assertEqual(result.schema_.default, 8)

    def test_nullable_object_param(self):
        result = AirflowService._param_to_input_description(
            "config_output_dir_generation",
            {
                "value": {"value": "s3://output/gen_config", "cid": "s3ovh"},
                "description": "Generation configuration output directory.",
                "schema": {
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "value": {
                            "type": "string",
                            "title": "Value",
                            "description": "Full path URI",
                        },
                        "cid": {"title": "Cid", "description": "Credential ID"},
                    },
                    "required": ["value"],
                },
            },
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.schema_.type, DataType.object)
        self.assertTrue(result.schema_.nullable)
        self.assertEqual(result.minOccurs, 0)
        self.assertIsNotNone(result.schema_.properties)
        self.assertIn("value", result.schema_.properties)
        self.assertIn("cid", result.schema_.properties)
        self.assertEqual(result.schema_.properties["value"].type, DataType.string)
        self.assertEqual(result.schema_.required, ["value"])
        self.assertEqual(
            result.schema_.default,
            {"value": "s3://output/gen_config", "cid": "s3ovh"},
        )

    def test_title_is_none_when_absent_from_schema(self):
        # When schema has no title, we leave it None so gavicore's _make_label
        # can produce a pretty label (e.g. "my_param" → "My Param").
        result = AirflowService._param_to_input_description(
            "my_param",
            {"value": 1, "description": "desc", "schema": {"type": "integer"}},
        )
        self.assertIsNotNone(result)
        self.assertIsNone(result.title)
        self.assertIsNone(result.schema_.title)

    def test_description_falls_back_to_schema_description(self):
        result = AirflowService._param_to_input_description(
            "my_param",
            {"value": 1, "schema": {"type": "integer", "description": "from schema"}},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.description, "from schema")

    def test_non_dict_param_returns_none(self):
        result = AirflowService._param_to_input_description("bad_param", "not a dict")
        self.assertIsNone(result)

    def test_missing_schema_key(self):
        result = AirflowService._param_to_input_description(
            "bare_param",
            {"value": 42},
        )
        self.assertIsNotNone(result)
        self.assertIsNone(result.schema_.type)
        self.assertEqual(result.schema_.default, 42)


class AirflowTokenProviderWiringTest(TestCase):
    """The service delegates bearer-token retrieval to a TokenProvider."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("wraptile.services.airflow.airflow_service.create_token_provider")
    def test_provider_created_once_and_reused(self, mock_create):
        mock_create.return_value = MagicMock(
            **{"get_token.return_value": "tok"},
        )
        service = AirflowService(title="t")
        service.configure(airflow_password="pw")  # noqa: S106

        self.assertIs(service.airflow_client, service.airflow_client)
        # The provider is built lazily, once, and re-consulted for each client
        # access so an expired token gets refreshed.
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_args.args[0], DEFAULT_AIRFLOW_BASE_URL)
        self.assertEqual(mock_create.return_value.get_token.call_count, 2)


def is_airflow_running(url: str, timeout: float = 1.0) -> bool:
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        return response.ok
    except requests.RequestException:
        return False


@unittest.skipUnless(
    is_airflow_running(DEFAULT_AIRFLOW_BASE_URL),
    reason=f"No Airflow server running on {DEFAULT_AIRFLOW_BASE_URL}",
)
class AirflowServiceTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = app
        self.restore_env = set_env(
            EOZILLA_SERVICE="wraptile.services.airflow:service",
        )
        ServiceProvider._service = None
        self.service = get_service()
        self.assertIsInstance(self.service, AirflowService)
        self.service.configure()

    async def asyncTearDown(self):
        self.restore_env()
        # comment out to check generated DAGs
        # shutil.rmtree(EOZILLA_AIRFLOW_DAGS_FOLDER, ignore_errors=True)

    def get_request(self) -> fastapi.Request:
        return fastapi.Request({"type": "http", "app": self.app, "headers": {}})

    async def test_get_capabilities(self):
        caps = await self.service.get_capabilities(request=self.get_request())
        self.assertIsInstance(caps, Capabilities)

    async def test_get_conformance(self):
        conf = await self.service.get_conformance(request=self.get_request())
        self.assertIsInstance(conf, ConformanceDeclaration)

    async def test_get_processes(self):
        processes = await self.service.get_processes(request=self.get_request())
        self.assertIsInstance(processes, ProcessList)

    async def test_get_process(self):
        process_list = await self.service.get_processes(request=self.get_request())
        processes = process_list.processes
        if not processes:
            warnings.warn("Skipping test; no Airflow processes found")
            return

        process = await self.service.get_process(
            process_id=processes[0].id, request=self.get_request()
        )
        self.assertIsInstance(process, ProcessDescription)
