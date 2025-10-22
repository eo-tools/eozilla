#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from IPython.core.interactiveshell import InteractiveShell

from s2gos_client import ClientError
from s2gos_client.api.ishell import exception_handler, has_ishell
from s2gos_common.models import ApiError


class IShellTest(TestCase):
    def test_has_ishell_ok(self):
        self.assertTrue(has_ishell)

    def test_exception_handler_ok(self):
        self.assertIsNotNone(exception_handler)
        self.assertTrue(callable(exception_handler))

    def test_exception_handler_with_client_exception(self):
        exc = ClientError(
            "What the heck", ApiError(type="error", title="Don't worry, be happy")
        )
        result = exception_handler(
            InteractiveShell.instance(),
            type(exc),
            exc,
            None,
        )
        self.assertEqual((None, None, None), result)

    def test_exception_handler_with_value_error(self):
        exc = ValueError("Too large")
        result = exception_handler(
            InteractiveShell.instance(),
            type(exc),
            exc,
            None,
        )
        self.assertEqual(None, result)
