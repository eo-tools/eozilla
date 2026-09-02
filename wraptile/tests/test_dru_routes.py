from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from gavicore.dru_models import (
    GenericExecutionUnit,
    OgcApplicationPackage,
    OgcApplicationPackageProcessDescription,
)
from gavicore.dru_service import DruService
from gavicore.models import ProcessDescription, ProcessSummary
from wraptile.dru_routes import (
    deploy_process,
    dru_router,
    get_formal_description,
    replace_process,
    undeploy_process,
)
from wraptile.provider import get_service

EXPECTED_ROUTES = [
    APIRoute(
        path="/processes",
        name="deploy_process",
        endpoint=deploy_process,
        methods=["POST"],
    ),
    APIRoute(
        path="/processes/{processId}",
        name="replace_process",
        endpoint=replace_process,
        methods=["PUT"],
    ),
    APIRoute(
        path="/processes/{processId}",
        name="undeploy_process",
        endpoint=undeploy_process,
        methods=["DELETE"],
    ),
    APIRoute(
        path="/processes/{processId}/package",
        name="get_formal_description",
        endpoint=get_formal_description,
        methods=["GET"],
    ),
]


# mocked_service.replace_process.return_value

mocked_request = AsyncMock(spec=Request)
mocked_response = AsyncMock(spec=Response)


class DruRoutesTest(IsolatedAsyncioTestCase):
    async def test_router_exposes_dru_routes(self):
        for route in dru_router.routes:
            with self.subTest(route=route):
                self.assertIn(route, EXPECTED_ROUTES)


class DruRouterTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mocked_service = AsyncMock(spec=DruService)
        self.app = FastAPI()
        self.app.include_router(dru_router)
        self.app.dependency_overrides[get_service] = lambda: self.mocked_service
        self.client = TestClient(self.app)

    async def test_deployment_calls_service_method(self):
        return_summary: ProcessSummary = ProcessSummary(
            id="placeholder-id", version="0.0.1"
        )

        self.mocked_service.deploy_process.return_value = return_summary

        response = self.client.post("/processes", json={})

        self.assertEqual(response.status_code, 201)

        self.assertDictEqual(
            response.json(),
            return_summary.model_dump(exclude_defaults=True, exclude_none=True),
        )

        self.mocked_service.deploy_process.assert_called_once()

    async def test_replacement_calls_service_method(self):
        return_summary: ProcessSummary = ProcessSummary(
            id="placeholder-id", version="0.0.2"
        )

        self.mocked_service.replace_process.return_value = return_summary

        response = self.client.put("/processes/placeholder-id", json={})

        self.assertEqual(response.status_code, 200)

        self.assertDictEqual(
            response.json(),
            return_summary.model_dump(exclude_defaults=True, exclude_none=True),
        )

        self.mocked_service.replace_process.assert_called_once()

    async def test_undeployment_calls_service_method(self):
        self.mocked_service.undeploy_process.return_value = None

        response = self.client.delete("/processes/placeholder-id")

        self.assertEqual(response.status_code, 204)

        self.mocked_service.undeploy_process.assert_called_once()

    async def test_formal_description_calls_service_method(self):
        return_summary: OgcApplicationPackage = OgcApplicationPackage(
            process_description=OgcApplicationPackageProcessDescription(
                process=ProcessDescription(id="placeholder-id", version="0.0.2")
            ),
            executionUnit=GenericExecutionUnit(type="something to execute"),
        )
        self.mocked_service.get_formal_description.return_value = return_summary

        response = self.client.get("/processes/placeholder-id/package")

        self.assertEqual(response.status_code, 200)

        self.assertDictEqual(
            response.json(),
            return_summary.model_dump(
                exclude_defaults=True, exclude_none=True, by_alias=True
            ),
        )

        self.mocked_service.get_formal_description.assert_called_once()
