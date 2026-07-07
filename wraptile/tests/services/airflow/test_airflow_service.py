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


_KEYCLOAK_ENV = {
    "KEYCLOAK_TOKEN_URL": "https://kc.example/realms/eozilla-auth/protocol/openid-connect/token",
    "WRAPTILE_CLIENT_ID": "wraptile",
    "WRAPTILE_CLIENT_SECRET": "s3cr3t",
}


class AirflowAccessTokenTest(TestCase):
    """The wraptile->airflow bearer-token logic (Keycloak vs. legacy basic)."""

    def _token_response(self, token: str = "kc-token", expires_in: int = 300):  # noqa: S107
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"access_token": token, "expires_in": expires_in}
        return resp

    @patch.dict("os.environ", _KEYCLOAK_ENV, clear=True)
    @patch("wraptile.services.airflow.airflow_service.requests.post")
    def test_keycloak_mode_selected_and_token_cached(self, mock_post):
        mock_post.return_value = self._token_response()
        service = AirflowService(title="t")

        # First call mints via client_credentials against the Keycloak token URL.
        token = service._airflow_access_token("https://airflow.internal:8443")
        self.assertEqual(token, "kc-token")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], _KEYCLOAK_ENV["KEYCLOAK_TOKEN_URL"])
        self.assertEqual(kwargs["data"]["grant_type"], "client_credentials")
        self.assertEqual(kwargs["data"]["client_id"], "wraptile")
        self.assertEqual(kwargs["data"]["audience"], "airflow")

        # Second call is served from cache — no extra network round-trip.
        self.assertEqual(
            service._airflow_access_token("https://airflow.internal:8443"), "kc-token"
        )
        mock_post.assert_called_once()

    @patch.dict("os.environ", _KEYCLOAK_ENV, clear=True)
    @patch("wraptile.services.airflow.airflow_service.requests.post")
    def test_keycloak_token_refreshed_when_expired(self, mock_post):
        mock_post.side_effect = [
            self._token_response("first"),
            self._token_response("second"),
        ]
        service = AirflowService(title="t")
        self.assertEqual(service._fetch_keycloak_service_token(), "first")
        # Force expiry, then a new token is fetched.
        service._service_token_expiry = 0.0
        self.assertEqual(service._fetch_keycloak_service_token(), "second")
        self.assertEqual(mock_post.call_count, 2)

    @patch.dict("os.environ", {}, clear=True)
    def test_basic_mode_requires_password(self):
        service = AirflowService(title="t")
        with self.assertRaises(RuntimeError):
            service._airflow_access_token(DEFAULT_AIRFLOW_BASE_URL)

    @patch.dict("os.environ", {}, clear=True)
    @patch.object(AirflowService, "fetch_access_token", return_value="airflow-native")
    def test_basic_mode_falls_back_to_native_token(self, mock_fetch):
        service = AirflowService(title="t")
        service.configure(airflow_password="pw", airflow_username="admin")  # noqa: S106
        self.assertEqual(
            service._airflow_access_token(DEFAULT_AIRFLOW_BASE_URL), "airflow-native"
        )
        mock_fetch.assert_called_once()


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
