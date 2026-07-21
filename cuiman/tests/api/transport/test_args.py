#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from cuiman.api.exceptions import ClientError
from cuiman.api.transport import TransportArgs
from cuiman.api.transport.args import CLIENT_ERROR_URI
from gavicore.models import ApiError


class TransportArgsTest(TestCase):
    def test_get_error_for_json_ok(self):
        args = TransportArgs("/jobs", method="get")
        client_error = args.get_exception_for_status(
            401,
            {
                "type": "https://world.of.errors.com/NoJobsError",
                "title": "No jobs",
                "status": 401,
            },
            "Not implemented",
        )
        self.assertIsInstance(client_error, ClientError)
        self.assertEqual("Not implemented (status 401)", f"{client_error}")
        self.assertIsInstance(client_error.api_error, ApiError)
        self.assertEqual(
            ApiError(
                type="https://world.of.errors.com/NoJobsError",
                title="No jobs",
                status=401,
            ),
            client_error.api_error,
        )

    def test_get_error_for_json_fail_1(self):
        args = TransportArgs("/jobs", method="get")
        client_error = args.get_exception_for_status(
            501, {"message": "Wrong error"}, "Not implemented"
        )
        self.assertIsInstance(client_error, ClientError)
        self.assertEqual("Not implemented (status 501)", f"{client_error}")
        self.assertIsInstance(client_error.api_error, ApiError)
        self.assertEqual(CLIENT_ERROR_URI, client_error.api_error.type)

    def test_get_error_for_json_fail_2(self):
        args = TransportArgs("/jobs", method="get")
        client_error = args.get_exception_for_status(501, 13, "Not implemented")
        self.assertIsInstance(client_error, ClientError)
        self.assertEqual("Not implemented (status 501)", f"{client_error}")
        self.assertIsInstance(client_error.api_error, ApiError)
        self.assertEqual(CLIENT_ERROR_URI, client_error.api_error.type)

    def test_invalid_uri_template(self):
        with self.assertRaises(ValueError):
            TransportArgs("/}}}}}", method="get")

    def test_uri_template_expansion_failed(self):
        with self.assertRaises(RuntimeError):
            args = TransportArgs("/jobs", method="get")
            # Easiest way to provoke a "None" result in template expansion
            # without __post_init__ catching the invalid template first.
            args.path = "/}}}}}"
            args.get_url("/jobs")
