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
from appligator.airflow.run_step import _XComEncoder, _pydantic_type, coerce_inputs, resolve_function


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

    def test_none_passthrough(self):
        def func(a: int):
            pass

        result = coerce_inputs(func, {"a": None})
        self.assertIsNone(result["a"])

    def test_json_fallback_parses_numeric_string(self):
        def func(x):  # no annotation — falls through to json.loads fallback
            pass

        result = coerce_inputs(func, {"x": "5.0"})
        self.assertEqual(result["x"], 5.0)

    def test_coerces_dict_to_pydantic_model(self):
        class MyModel(BaseModel):
            path: str

        def func(ref: MyModel):
            pass

        result = coerce_inputs(func, {"ref": {"path": "/tmp/foo"}})
        self.assertIsInstance(result["ref"], MyModel)
        self.assertEqual(result["ref"].path, "/tmp/foo")

    def test_coerces_json_string_to_pydantic_model(self):
        class MyModel(BaseModel):
            path: str

        def func(ref: MyModel):
            pass

        result = coerce_inputs(func, {"ref": '{"path": "/tmp/bar"}'})
        self.assertIsInstance(result["ref"], MyModel)
        self.assertEqual(result["ref"].path, "/tmp/bar")

    def test_coerces_python_repr_string_to_pydantic_model(self):
        class MyModel(BaseModel):
            path: str

        def func(ref: MyModel):
            pass

        # Single-quoted Python repr — invalid JSON, valid ast.literal_eval
        result = coerce_inputs(func, {"ref": "{'path': '/tmp/baz'}"})
        self.assertIsInstance(result["ref"], MyModel)
        self.assertEqual(result["ref"].path, "/tmp/baz")

    def test_unwraps_return_value_wrapper_before_model_construction(self):
        class MyModel(BaseModel):
            path: str

        def func(ref: MyModel):
            pass

        # Procodile Workflow returns {"return_value": actual_value}
        result = coerce_inputs(func, {"ref": {"return_value": {"path": "/data"}}})
        self.assertIsInstance(result["ref"], MyModel)
        self.assertEqual(result["ref"].path, "/data")

    def test_no_coercion_when_already_model_instance(self):
        class MyModel(BaseModel):
            path: str

        def func(ref: MyModel):
            pass

        existing = MyModel(path="/existing")
        result = coerce_inputs(func, {"ref": existing})
        self.assertIs(result["ref"], existing)

    def test_optional_pydantic_model_coercion(self):
        class MyModel(BaseModel):
            path: str

        def func(ref: typing.Optional[MyModel] = None):
            pass

        result = coerce_inputs(func, {"ref": {"path": "/opt"}})
        self.assertIsInstance(result["ref"], MyModel)
        self.assertEqual(result["ref"].path, "/opt")


class TestPydanticType(unittest.TestCase):
    def test_direct_basemodel_subclass(self):
        class MyModel(BaseModel):
            x: int

        self.assertIs(_pydantic_type(MyModel), MyModel)

    def test_optional_basemodel(self):
        class MyModel(BaseModel):
            x: int

        self.assertIs(_pydantic_type(typing.Optional[MyModel]), MyModel)

    def test_non_model_type_returns_none(self):
        self.assertIsNone(_pydantic_type(int))

    def test_non_type_hint_returns_none(self):
        self.assertIsNone(_pydantic_type(None))


class TestResolveFunction(unittest.TestCase):
    def _make_module(self, name, **attrs):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod
        return mod

    def tearDown(self):
        for key in list(sys.modules):
            if key.startswith("_test_resolve_"):
                del sys.modules[key]

    def test_resolves_simple_function(self):
        def my_func():
            return 42

        self._make_module("_test_resolve_simple", my_func=my_func)
        self.assertIs(resolve_function("_test_resolve_simple", "my_func"), my_func)

    def test_resolves_nested_attribute(self):
        inner = types.SimpleNamespace(value=99)
        self._make_module("_test_resolve_nested", inner=inner)
        self.assertIs(resolve_function("_test_resolve_nested", "inner.value"), 99)

    def test_procodile_registry_fallback(self):
        step_func = lambda: "result"  # noqa: E731
        step = types.SimpleNamespace(function=step_func)
        registry = types.SimpleNamespace(main={"step_id": step})
        workflow = types.SimpleNamespace(registry=registry)
        self._make_module("_test_resolve_registry", my_workflow=workflow)

        result = resolve_function("_test_resolve_registry", "my_workflow.function")
        self.assertIs(result, step_func)

    def test_procodile_empty_registry_raises_attribute_error(self):
        registry = types.SimpleNamespace(main={})
        workflow = types.SimpleNamespace(registry=registry)
        self._make_module("_test_resolve_empty_registry", my_workflow=workflow)

        with self.assertRaises(AttributeError) as ctx:
            resolve_function("_test_resolve_empty_registry", "my_workflow.function")
        self.assertIn("no main step", str(ctx.exception))

    def test_non_function_attribute_error_reraises(self):
        workflow = types.SimpleNamespace()  # no .missing attr
        self._make_module("_test_resolve_reraised", workflow=workflow)

        with self.assertRaises(AttributeError):
            resolve_function("_test_resolve_reraised", "workflow.missing")

    def test_step_function_unwrap(self):
        bare_func = lambda: "bare"  # noqa: E731
        step = types.SimpleNamespace(function=bare_func)
        self._make_module("_test_resolve_step", my_step=step)

        result = resolve_function("_test_resolve_step", "my_step")
        self.assertIs(result, bare_func)
