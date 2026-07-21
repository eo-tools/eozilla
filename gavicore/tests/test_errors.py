#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from gavicore.models import ApiError
from gavicore.service import errors


# noinspection PyMethodMayBeStatic
class ErrorsTest(TestCase):
    def test_is_error_type_id(self):
        self.assertTrue(errors.is_error_type_id("bad-request"))
        self.assertFalse(errors.is_error_type_id("definitely-not-valid"))

    def test_get_error_type_uri_for_ogc_problem(self):
        self.assertEqual(
            "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-job",
            errors.get_error_type_uri("no-such-job"),
        )

    def test_get_error_type_uri_for_eozilla_problem(self):
        self.assertEqual(
            "https://eo-tools.github.io/eozilla/problems#bad-request",
            errors.get_error_type_uri("bad-request"),
        )

    def test_get_error_type_uri_rejects_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown type_id: unknown-problem"):
            errors.get_error_type_uri("unknown-problem")  # type: ignore[arg-type]

    def test_get_error_type_id_for_known_status(self):
        self.assertEqual("unauthorized", errors.get_error_type_id(401))
        self.assertEqual("unsupported-media-type", errors.get_error_type_id(415))

    def test_get_error_type_id_for_job_problem(self):
        self.assertEqual(
            "no-such-job", errors.get_error_type_id(404, is_job_problem=True)
        )

    def test_get_error_type_id_falls_back_to_default(self):
        self.assertEqual("internal-server-error", errors.get_error_type_id(418))
        self.assertEqual("conflict", errors.get_error_type_id(418, default="conflict"))

    def test_create_api_error_without_exception(self):
        api_error = errors.create_api_error(
            "forbidden",
            status=403,
            title="Forbidden",
            detail="No access.",
            instance="/jobs/42",
        )

        self.assertEqual(
            ApiError(
                type="https://eo-tools.github.io/eozilla/problems#forbidden",
                status=403,
                title="Forbidden",
                detail="No access.",
                instance="/jobs/42",
            ),
            api_error,
        )

    def test_create_api_error_from_exception(self):
        try:
            raise RuntimeError("Boom")
        except RuntimeError as exc:
            runtime_error = exc

        api_error = errors.create_api_error(
            "internal-server-error",
            exception=runtime_error,
            status=500,
            detail="The request failed.",
        )

        self.assertEqual(
            "https://eo-tools.github.io/eozilla/problems#internal-server-error",
            api_error.type,
        )
        self.assertEqual("Boom", api_error.title)
        self.assertEqual(500, api_error.status)
        self.assertEqual("The request failed.", api_error.detail)
        self.assertIsInstance(api_error.traceback, list)
        self.assertTrue(api_error.traceback)

    def test_create_api_error_keeps_explicit_traceback_and_title(self):
        api_error = errors.create_api_error(
            "conflict",
            exception=RuntimeError("Boom"),
            title="Already set",
            traceback="traceback text",
        )

        self.assertEqual("Already set", api_error.title)
        self.assertEqual("traceback text", api_error.traceback)

    def test_create_api_error_rejects_invalid_type_id(self):
        with pytest.raises(ValueError, match="Unknown type_id: unknown-problem"):
            # noinspection PyTypeChecker
            errors.create_api_error("unknown-problem")

    def test_create_api_error_rejects_non_string_type_id(self):
        with pytest.raises(TypeError, match="type_id must have type str, but was int"):
            errors.create_api_error(1)  # type: ignore[arg-type]

    def test_create_api_error_rejects_non_exception_exc(self):
        with pytest.raises(
            TypeError, match="exc must have type BaseException, but was str"
        ):
            errors.create_api_error("bad-request", exception="boom")  # type: ignore[arg-type]
