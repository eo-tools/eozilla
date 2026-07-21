#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from gavicore.models import ApiError
from wraptile.exceptions import ServiceConfigException, ServiceException


class JSONContentExceptionTest(TestCase):
    def test_content_is_api_error_model(self):
        exc = ServiceException(401, "Bibo not authorized")
        self.assertEqual(
            ApiError(
                type="https://eo-tools.github.io/eozilla/problems#unauthorized",
                status=401,
                title="Unauthorized",
                detail="Bibo not authorized",
            ),
            exc.content,
        )

    def test_includes_traceback(self):
        try:
            raise RuntimeError("Argh!")
        except Exception as e:
            exc = ServiceException(500, "Internal error", exception=e)
            self.assertIsInstance(exc.content, ApiError)
            self.assertEqual(
                "https://eo-tools.github.io/eozilla/problems#internal-server-error",
                exc.content.type,
            )
            self.assertEqual("Argh!", exc.content.title)
            self.assertIsInstance(exc.content.traceback, list)

    def test_job_problem_uses_no_such_job_type(self):
        exc = ServiceException(404, "Result not found", is_job_problem=True)

        self.assertEqual(
            "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-job",
            exc.content.type,
        )
        self.assertEqual("Not Found", exc.content.title)

    def test_explicit_type_id_overrides_status_mapping(self):
        exc = ServiceException(404, "No permission", type_id="forbidden")

        self.assertEqual(
            "https://eo-tools.github.io/eozilla/problems#forbidden",
            exc.content.type,
        )

    def test_service_config_exception_uses_config_problem_type(self):
        exc = ServiceConfigException("Broken config")

        self.assertEqual(500, exc.content.status)
        self.assertEqual(
            "https://eo-tools.github.io/eozilla/problems#internal-server-config-error",
            exc.content.type,
        )
        self.assertEqual("Broken config", exc.content.detail)
        self.assertIsInstance(exc.content.traceback, list)
