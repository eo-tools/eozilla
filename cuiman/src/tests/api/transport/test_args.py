#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from s2gos_client.api.exceptions import ClientError
from s2gos_client.api.transport import TransportArgs
from s2gos_common.models import ApiError


class TransportArgsTest(TestCase):
    def test_get_error_for_json_ok(self):
        args = TransportArgs("/jobs", method="get")
        client_error = args.get_exception_for_status(
            401,
            "Not implemented",
            {"type": "ValueError", "title": "No jobs", "status": 401},
        )
        self.assertIsInstance(client_error, ClientError)
        self.assertEqual("Not implemented (status 401)", f"{client_error}")
        self.assertIsInstance(client_error.api_error, ApiError)
        self.assertEqual(
            ApiError(type="ValueError", title="No jobs", status=401),
            client_error.api_error,
        )

    def test_get_error_for_json_fail_1(self):
        args = TransportArgs("/jobs", method="get")
        client_error = args.get_exception_for_status(
            501, "Not implemented", {"message": "Wrong error"}
        )
        self.assertIsInstance(client_error, ClientError)
        self.assertEqual("Not implemented (status 501)", f"{client_error}")
        self.assertIsInstance(client_error.api_error, ApiError)
        self.assertEqual("ValidationError", client_error.api_error.type)

    def test_get_error_for_json_fail_2(self):
        args = TransportArgs("/jobs", method="get")
        client_error = args.get_exception_for_status(501, "Not implemented", 13)
        self.assertIsInstance(client_error, ClientError)
        self.assertEqual("Not implemented (status 501)", f"{client_error}")
        self.assertIsInstance(client_error.api_error, ApiError)
        self.assertEqual("ValidationError", client_error.api_error.type)
