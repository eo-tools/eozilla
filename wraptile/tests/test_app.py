#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from wraptile.app import load_app_eagerly
from wraptile.exceptions import ServiceConfigException
from wraptile.logging import LogMessageFilter
from wraptile.main import app


class AppLifecyleTest(IsolatedAsyncioTestCase):
    @patch("wraptile.app.get_service")
    async def test_lifespan_gets_service(self, patched_get_service):
        async with load_app_eagerly(app):
            patched_get_service.assert_called_once()

    @patch(
        "wraptile.app.get_service",
        side_effect=ServiceConfigException("Startup failed."),
    )
    async def test_get_service_fail_aborts_app(self, patched_get_service):
        with self.assertRaises(ServiceConfigException):
            async with load_app_eagerly(app):
                self.fail("Startup should not complete.")

        patched_get_service.assert_called_once()


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
