#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from s2gos_common.models import ApiError
from s2gos_server.exceptions import ServiceException


class JSONContentExceptionTest(TestCase):
    def test_content_is_api_error_model(self):
        exc = ServiceException(401, "Bibo not authorized")
        self.assertEqual(
            ApiError(
                type="ApiError",
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
            self.assertIsInstance(exc.content.traceback, list)
