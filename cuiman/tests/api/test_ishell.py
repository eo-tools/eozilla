#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import sys
from unittest import TestCase
from unittest.mock import patch

from IPython.core.interactiveshell import InteractiveShell

from cuiman import ClientError
from cuiman.api.ishell import exception_handler, has_ishell
from gavicore.models import ApiError


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


def test_ishell_without_ipython(monkeypatch):
    # Remove any cached copy so the top-level code runs again

    sys.modules.pop("cuiman.api.ishell", None)

    # Patch find_spec to simulate missing IPython
    with patch("importlib.util.find_spec", return_value=None):
        # Now import the module fresh
        import cuiman.api.ishell as ishell

        assert ishell.has_ishell is False
        assert ishell.exception_handler is None


def test_ishell_without_interactiveshell(monkeypatch):
    # Remove any cached copy so the top-level code runs again

    sys.modules.pop("cuiman.api.ishell", None)

    # Patch find_spec to simulate missing IPython
    with patch("importlib.util.find_spec", side_effect=ModuleNotFoundError):
        # Now import the module fresh
        import cuiman.api.ishell as ishell

        assert ishell.has_ishell is False
        assert ishell.exception_handler is None
