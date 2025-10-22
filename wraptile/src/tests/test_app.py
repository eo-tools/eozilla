#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging
from unittest import TestCase

from fastapi.testclient import TestClient

from s2gos_server.logging import LogMessageFilter
from s2gos_server.main import app
from s2gos_server.provider import ServiceProvider
from s2gos_server.services.local.testing import service

client = TestClient(app)


class AppTest(TestCase):
    def setUp(self):
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
                "type": "ApiError",
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


class LogMessageFilterTest(TestCase):
    def test_filter_works(self):
        class MyHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records: list[logging.LogRecord] = []

            def emit(self, record: logging.LogRecord):
                self.records.append(record)

        handler = MyHandler()
        logger = logging.getLogger("uvicorn.access")
        logger.addHandler(handler)
        logger.addFilter(LogMessageFilter("GET /jobs/"))
        logger.setLevel(logging.INFO)
        # excluded
        logger.info('INFO:     127.0.0.1:53529 - "GET /jobs/job_8 HTTP/1.1" 200 OK')
        logger.info('INFO:     127.0.0.1:53529 - "GET /jobs/job_9 HTTP/1.1" 200 OK')
        self.assertEqual(0, len(handler.records))
        # included
        logger.info('INFO:     127.0.0.1:53529 - "GET /jobs HTTP/1.1" 200 OK')
        self.assertEqual(1, len(handler.records))
        # included
        logger.info('INFO:     127.0.0.1:53529 - "GET /processes HTTP/1.1" 200 OK')
        self.assertEqual(2, len(handler.records))
