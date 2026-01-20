import json
import os
import tempfile
import types
import unittest
from pathlib import Path

from appligator.airflow import run_step


def make_test_module():
    mod = types.ModuleType("test_module")

    def add(a, b):
        return a + b

    def pair(a, b):
        return a, b

    mod.add = add
    mod.pair = pair
    return mod


import sys

sys.modules["test_module"] = make_test_module()


class TestRunStep(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AIRFLOW_XCOM_DIR"] = self.tmpdir.name

        import sys

        sys.modules["test_module"] = make_test_module()

    def tearDown(self):
        self.tmpdir.cleanup()
        os.environ.pop("AIRFLOW_XCOM_DIR", None)

    def test_main_single_output(self):
        run_step.main(
            func_module="test_module",
            func_qualname="add",
            inputs={"a": 2, "b": 3},
            output_keys=["sum"],
        )

        data = json.loads(Path(self.tmpdir.name, "return.json").read_text())
        self.assertEqual(data, {"sum": 5})

    def test_main_tuple_output(self):
        run_step.main(
            func_module="test_module",
            func_qualname="pair",
            inputs={"a": 1, "b": 2},
            output_keys=["x", "y"],
        )

        data = json.loads(Path(self.tmpdir.name, "return.json").read_text())
        self.assertEqual(data, {"x": 1, "y": 2})

    def test_main_default_output(self):
        run_step.main(
            func_module="test_module",
            func_qualname="add",
            inputs={"a": 4, "b": 6},
            output_keys=None,
        )

        data = json.loads(Path(self.tmpdir.name, "return.json").read_text())
        self.assertEqual(data, {"return_value": 10})
