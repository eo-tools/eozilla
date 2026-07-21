#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import os
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import pytest

from cuiman import ClientConfig
from cuiman.api.async_client import AsyncClient
from cuiman.api.auth.login import LoginResult
from gavicore.models import (
    ApiError,
    Capabilities,
    ConformanceDeclaration,
    JobInfo,
    JobList,
    JobResults,
    ProcessDescription,
    ProcessList,
    ProcessRequest,
)
from gavicore.util.request import ExecutionRequest

from ..helpers import MockTransport


class AsyncClientTest(IsolatedAsyncioTestCase):
    # noinspection PyPep8Naming
    async def asyncSetUp(self):
        self.transport = MockTransport()
        self.client = AsyncClient(
            api_url="https://acme.ogc.org/api", _transport=self.transport
        )

    def test_no_api_url(self):
        with pytest.raises(
            ValueError, match="Required setting 'api_url' not configured"
        ):
            AsyncClient(api_url="", _transport=self.transport)

    async def test_config(self):
        self.assertIsInstance(self.client.config, ClientConfig)

    async def test_repr_json(self):
        result = self.client._repr_json_()
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, len(result))
        data, metadata = result
        self.assertIsInstance(data, dict)
        self.assertIsInstance(metadata, dict)
        self.assertEqual({"root": "Client configuration:"}, metadata)

    async def test_create_execution_request(self):
        request = await self.client.create_execution_request(
            process_id="ID-1",
        )
        self.assertEqual(
            ExecutionRequest(process_id="ID-1", inputs={}),
            request,
        )

    async def test_create_execution_request_dotpath(self):
        request = await self.client.create_execution_request(
            process_id="ID-1", dotpath=True
        )
        self.assertEqual(
            ExecutionRequest(process_id="ID-1", inputs={}, dotpath=True),
            request,
        )

    async def test_get_capabilities(self):
        result = await self.client.get_capabilities()
        self.assertIsInstance(result, Capabilities)

    def test_default_transport_is_created_from_config(self):
        return_type_map = {JobInfo: dict}
        with (
            patch.object(ClientConfig, "return_type_map", return_type_map),
            # Isolate from any real ~/.eozilla/config on the developer's machine,
            # which would otherwise inject a logged-in token into the headers.
            # os.devnull is not a directory, so this path can never exist.
            patch.object(
                ClientConfig, "default_path", Path(os.devnull, ".eozilla", "config")
            ),
            patch("cuiman.api.async_client.HttpxTransport") as httpx_transport_cls,
        ):
            transport = httpx_transport_cls.return_value

            client = AsyncClient(
                api_url="https://acme.ogc.org/api",
                _debug=True,
            )

        self.assertIs(client._transport, transport)
        httpx_transport_cls.assert_called_once()
        _, kwargs = httpx_transport_cls.call_args
        self.assertEqual("https://acme.ogc.org/api/", kwargs["api_url"])
        self.assertEqual({}, kwargs["headers"])
        self.assertIs(return_type_map, kwargs["return_type_map"])
        self.assertIsNone(kwargs["async_token_refresher"])
        self.assertTrue(kwargs["debug"])

    async def test_default_transport_receives_login_auth_and_refresh_callback(self):
        old_access = "old-access-token"
        old_refresh = "old-refresh-token"
        new_access = "new-access-token"
        new_refresh = "new-refresh-token"

        with patch("cuiman.api.async_client.HttpxTransport") as httpx_transport_cls:
            client = AsyncClient(
                api_url="https://acme.ogc.org/api",
                auth_type="login",
                token=old_access,
                refresh_token=old_refresh,
            )

        _, kwargs = httpx_transport_cls.call_args
        self.assertEqual(
            {"Authorization": f"Bearer {old_access}"},
            kwargs["headers"],
        )
        async_token_refresher = kwargs["async_token_refresher"]
        self.assertIsNotNone(async_token_refresher)

        with patch(
            "cuiman.api.auth.login_async.refresh_login_async",
            new_callable=AsyncMock,
            return_value=LoginResult(
                access_token=new_access,
                refresh_token=new_refresh,
            ),
        ) as refresh_login_async:
            refreshed_headers = await async_token_refresher()

        refresh_login_async.assert_awaited_once_with(client.config)
        self.assertEqual(
            {"Authorization": f"Bearer {new_access}"},
            refreshed_headers,
        )
        self.assertEqual(new_access, client.config.token)
        self.assertEqual(new_refresh, client.config.refresh_token)

    async def test_transport_args_for_all_endpoints(self):
        request = ProcessRequest(inputs={"bbox": [10, 20, 30, 40]}, outputs={})
        scenarios = [
            (
                lambda: self.client.get_capabilities(timeout=10),
                Capabilities,
                {
                    "path": "/",
                    "method": "get",
                    "return_types": {"200": Capabilities},
                    "error_types": {"500": ApiError},
                    "extra_kwargs": {"timeout": 10},
                },
            ),
            (
                lambda: self.client.get_conformance(headers={"X-Test": "yes"}),
                ConformanceDeclaration,
                {
                    "path": "/conformance",
                    "method": "get",
                    "return_types": {"200": ConformanceDeclaration},
                    "error_types": {"500": ApiError},
                    "extra_kwargs": {"headers": {"X-Test": "yes"}},
                },
            ),
            (
                lambda: self.client.get_processes(params={"limit": 5}),
                ProcessList,
                {
                    "path": "/processes",
                    "method": "get",
                    "return_types": {"200": ProcessList},
                    "extra_kwargs": {"params": {"limit": 5}},
                },
            ),
            (
                lambda: self.client.get_process("gobabeb_1", follow_redirects=True),
                ProcessDescription,
                {
                    "path": "/processes/{processID}",
                    "method": "get",
                    "path_params": {"processID": "gobabeb_1"},
                    "return_types": {"200": ProcessDescription},
                    "error_types": {"404": ApiError},
                    "extra_kwargs": {"follow_redirects": True},
                },
            ),
            (
                lambda: self.client.execute_process("gobabeb_1", request, timeout=60),
                JobInfo,
                {
                    "path": "/processes/{processID}/execution",
                    "method": "post",
                    "path_params": {"processID": "gobabeb_1"},
                    "request": request,
                    "return_types": {"201": JobInfo},
                    "error_types": {"404": ApiError, "500": ApiError},
                    "extra_kwargs": {"timeout": 60},
                },
            ),
            (
                lambda: self.client.get_jobs(timeout=20),
                JobList,
                {
                    "path": "/jobs",
                    "method": "get",
                    "return_types": {"200": JobList},
                    "error_types": {"404": ApiError},
                    "extra_kwargs": {"timeout": 20},
                },
            ),
            (
                lambda: self.client.get_job("job_12", timeout=30),
                JobInfo,
                {
                    "path": "/jobs/{jobId}",
                    "method": "get",
                    "path_params": {"jobId": "job_12"},
                    "return_types": {"200": JobInfo},
                    "error_types": {"404": ApiError, "500": ApiError},
                    "extra_kwargs": {"timeout": 30},
                },
            ),
            (
                lambda: self.client.dismiss_job("job_12", timeout=40),
                JobInfo,
                {
                    "path": "/jobs/{jobId}",
                    "method": "delete",
                    "path_params": {"jobId": "job_12"},
                    "return_types": {"200": JobInfo},
                    "error_types": {"404": ApiError, "500": ApiError},
                    "extra_kwargs": {"timeout": 40},
                },
            ),
            (
                lambda: self.client.get_job_results("job_12", timeout=50),
                JobResults,
                {
                    "path": "/jobs/{jobId}/results",
                    "method": "get",
                    "path_params": {"jobId": "job_12"},
                    "return_types": {"200": JobResults},
                    "error_types": {"404": ApiError, "500": ApiError},
                    "extra_kwargs": {"timeout": 50},
                },
            ),
        ]

        for call, result_type, expected in scenarios:
            with self.subTest(path=expected["path"]):
                self.transport.async_calls.clear()

                result = await call()

                self.assertIsInstance(result, result_type)
                self.assertEqual(1, len(self.transport.async_calls))
                args = self.transport.async_calls[0]
                for name, value in expected.items():
                    self.assertEqual(value, getattr(args, name))
                self.assertEqual(
                    expected.get("path_params", {}),
                    args.path_params,
                )
                self.assertEqual(
                    expected.get("request"),
                    args.request,
                )
                self.assertEqual(
                    expected.get("error_types", {}),
                    args.error_types,
                )

    def test_custom_transport_is_used_without_creating_httpx_transport(self):
        with patch("cuiman.api.async_client.HttpxTransport") as httpx_transport_cls:
            client = AsyncClient(
                api_url="https://acme.ogc.org/api",
                _transport=self.transport,
            )

        self.assertIs(client._transport, self.transport)
        httpx_transport_cls.assert_not_called()

    async def test_close_without_transport_is_noop(self):
        self.client._transport = None

        await self.client.close()

        self.assertIsNone(self.client._transport)

    async def test_get_conformance(self):
        result = await self.client.get_conformance()
        self.assertIsInstance(result, ConformanceDeclaration)

    async def test_get_processes(self):
        result = await self.client.get_processes()
        self.assertIsInstance(result, ProcessList)

    async def test_get_process(self):
        result = await self.client.get_process(process_id="gobabeb_1")
        self.assertIsInstance(result, ProcessDescription)

    async def test_execute_process(self):
        result = await self.client.execute_process(
            process_id="gobabeb_1",
            request=ProcessRequest(
                inputs={"bbox": [10, 20, 30, 40]},
                outputs={},
            ),
        )
        self.assertIsInstance(result, JobInfo)

    async def test_get_jobs(self):
        result = await self.client.get_jobs()
        self.assertIsInstance(result, JobList)

    async def test_dismiss_job(self):
        result = await self.client.dismiss_job("job_12")
        self.assertIsInstance(result, JobInfo)

    async def test_get_job(self):
        result = await self.client.get_job("job_12")
        self.assertIsInstance(result, JobInfo)

    async def test_get_job_results(self):
        result = await self.client.get_job_results("job_12")
        self.assertIsInstance(result, JobResults)

    async def test_close(self):
        self.assertFalse(self.transport.closed)
        await self.client.close()
        self.assertTrue(self.transport.closed)
