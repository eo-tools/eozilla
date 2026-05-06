#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
import os
import sys
import tempfile
import types
import typing
import unittest
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from appligator.airflow import run_step
from appligator.airflow.run_step import _XComEncoder, coerce_inputs


def make_test_module():
    mod = types.ModuleType("test_module")

    def add(a, b):
        return a + b

    def pair(a, b):
        return a, b

    mod.add = add
    mod.pair = pair
    return mod


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


class TestXComEncoder(unittest.TestCase):
    def test_pydantic_model(self):
        class MyModel(BaseModel):
            x: int
            y: str

        obj = MyModel(x=1, y="hello")
        result = json.dumps(obj, cls=_XComEncoder)
        self.assertEqual(json.loads(result), {"x": 1, "y": "hello"})

    def test_fallback_to_str(self):
        class Unserializable:
            def __str__(self):
                return "custom_repr"

        result = json.dumps(Unserializable(), cls=_XComEncoder)
        self.assertEqual(json.loads(result), "custom_repr")


class TestCoerceInputs(unittest.TestCase):
    def test_coerces_string_to_int(self):
        def func(a: int, b: str):
            pass

        result = coerce_inputs(func, {"a": "42", "b": "hello"})
        self.assertEqual(result, {"a": 42, "b": "hello"})
        self.assertIsInstance(result["a"], int)

    def test_coerces_string_to_float(self):
        def func(x: float):
            pass

        result = coerce_inputs(func, {"x": "3.14"})
        self.assertAlmostEqual(result["x"], 3.14)

    def test_coerces_string_to_bool(self):
        def func(flag: bool):
            pass

        result = coerce_inputs(func, {"flag": "True"})
        self.assertEqual(result["flag"], True)

    def test_no_coercion_when_already_correct_type(self):
        def func(a: int):
            pass

        result = coerce_inputs(func, {"a": 5})
        self.assertEqual(result["a"], 5)
        self.assertIsInstance(result["a"], int)

    def test_returns_inputs_unchanged_on_introspection_failure(self):
        # Simulate a function whose type hints can't be resolved
        def func(a: "NonExistentType"):  # noqa: F821
            pass

        # Patch get_type_hints to raise
        original = typing.get_type_hints

        def raise_error(*args, **kwargs):
            raise NameError("name 'NonExistentType' is not defined")

        typing.get_type_hints = raise_error
        try:
            result = coerce_inputs(func, {"a": "value"})
            self.assertEqual(result, {"a": "value"})
        finally:
            typing.get_type_hints = original
