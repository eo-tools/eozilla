#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import sys
from unittest import TestCase
from unittest.mock import patch

from IPython.core.interactiveshell import InteractiveShell

from cuiman import ClientError
from cuiman.api.ishell import has_ishell
from gavicore.models import ApiError


class IShellTest(TestCase):
    handler = None

    @classmethod
    def setUpClass(cls):
        from cuiman.api.ishell import _register_exception_handler

        InteractiveShell.instance()  # ensure a shell exists before registering
        # staticmethod prevents Python from binding the TestCase instance as `self`
        # when the handler is accessed via self.handler — the handler's own `self`
        # param expects an InteractiveShell, not a TestCase.
        cls.handler = staticmethod(_register_exception_handler())

    def test_has_ishell_ok(self):
        self.assertTrue(has_ishell)

    def test_exception_handler_ok(self):
        self.assertIsNotNone(self.handler)
        self.assertTrue(callable(self.handler))

    def test_exception_handler_with_client_exception(self):
        exc = ClientError(
            "What the heck", ApiError(type="error", title="Don't worry, be happy")
        )
        result = self.handler(
            InteractiveShell.instance(),
            type(exc),
            exc,
            None,
        )
        self.assertEqual((None, None, None), result)

    def test_exception_handler_with_value_error(self):
        exc = ValueError("Too large")
        result = self.handler(
            InteractiveShell.instance(),
            type(exc),
            exc,
            None,
        )
        self.assertEqual(None, result)


def test_ishell_registers_handler_when_shell_already_initialized():
    # Covers the module-level branch: has_ishell=True AND initialized()=True
    InteractiveShell.instance()  # idempotent; ensures initialized() returns True
    sys.modules.pop("cuiman.api.ishell", None)
    import cuiman.api.ishell as ishell

    assert ishell.exception_handler is not None
    assert callable(ishell.exception_handler)


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
