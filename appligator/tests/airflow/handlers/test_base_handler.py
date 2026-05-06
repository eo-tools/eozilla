#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import unittest

from appligator.airflow.handlers.base_handler import OperatorHandler
from appligator.airflow.models import TaskIR


class TestOperatorHandlerBase(unittest.TestCase):
    """
    Tests the abstract OperatorHandler contract.
    """

    def test_supports_not_implemented(self):
        handler = OperatorHandler()
        task = TaskIR(id="t", runtime="kubernetes", inputs={})

        with self.assertRaises(NotImplementedError):
            handler.supports(task)

    def test_render_not_implemented(self):
        handler = OperatorHandler()
        task = TaskIR(id="t", runtime="kubernetes", inputs={})

        with self.assertRaises(NotImplementedError):
            handler.render(task)
