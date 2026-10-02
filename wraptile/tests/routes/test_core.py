#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

"""Tests for OGC API - Processes Part 1: Core routes."""

from unittest import TestCase

from fastapi.testclient import TestClient

from wraptile.main import app
from wraptile.provider import ServiceProvider
from wraptile.services.local.testing import service

client = TestClient(app)


class CoreRoutesTest(TestCase):
    def setUp(self):
        service.configure()
        ServiceProvider.set_instance(service)

    def test_get_capabilities(self):
        response = client.get("/")
        self.assertEqual(200, response.status_code)

    def test_get_conformance(self):
        response = client.get("/conformance")
        self.assertEqual(200, response.status_code)

    def test_get_processes(self):
        response = client.get("/processes")
        self.assertEqual(200, response.status_code)

    def test_get_process(self):
        response = client.get("/processes/primes_between")
        self.assertEqual(200, response.status_code)

    def test_get_process_fail(self):
        response = client.get("/processes/primos_batman")
        self.assertEqual(404, response.status_code)
        self.assertEqual(
            {
                "type": "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process",
                "status": 404,
                "title": "Not Found",
                "detail": "Process 'primos_batman' does not exist",
            },
            response.json(),
        )

    def test_execute_process(self):
        response = client.post("/processes/primes_between/execution", json={})
        self.assertEqual(201, response.status_code)

    def test_get_jobs(self):
        response = client.post("/processes/primes_between/execution", json={})
        _job_id = response.json()["jobID"]
        response = client.get("/jobs")
        self.assertEqual(200, response.status_code)

    def test_get_job(self):
        response = client.post("/processes/primes_between/execution", json={})
        job_id = response.json()["jobID"]
        response = client.get(f"/jobs/{job_id}")
        self.assertEqual(200, response.status_code)

    def test_dismiss_job(self):
        response = client.post("/processes/primes_between/execution", json={})
        job_id = response.json()["jobID"]
        response = client.delete(f"/jobs/{job_id}")
        self.assertEqual(200, response.status_code)

    def test_get_job_results(self):
        response = client.post("/processes/primes_between/execution", json={})
        job_info = response.json()
        job_id = response.json()["jobID"]
        while job_info.get("status") != "successful":
            response = client.get(f"/jobs/{job_id}")
            job_info = response.json()
        response = client.get(f"/jobs/{job_id}/results")
        self.assertEqual(200, response.status_code)
