#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated
from unittest import TestCase

import pydantic
import pytest
from pydantic import BaseModel, Field

from s2gos_common.models import (
    DataType,
    InputDescription,
    OutputDescription,
    ProcessDescription,
    Schema,
)
from s2gos_common.process import JobContext, Process
from s2gos_common.util.testing import BaseModelMixin


def f1(x: float, y: float) -> float:
    """This is f1."""
    return 2.0 * y if x else 0.5 * y


def f2(a: bool | None, b: float | bool) -> tuple[float, float]:
    """This is f2."""
    return (2.0 * b, 0.5 * b) if a else (0.5 * b, 2.0 * b)


class Point(BaseModel):
    """A 2-D point."""

    x: float = Field(0.0, title="X-coordinate")
    y: float = Field(0.0, title="Y-coordinate")


def f3(point1: Point, point2: Point) -> Point:
    """This is f3."""
    return Point(x=(point2.x - point1.x), y=(point2.y - point1.y))


def f4(ctx: JobContext, flag: bool) -> str:
    """This is f3."""
    return f"{type(ctx).__name__}-{flag}"


def f4_fail_ctx(ctx: JobContext, flag: bool, ctx2: JobContext) -> str:
    """This is f4 with two context definitions -> illegal."""
    return f"{type(ctx).__name__}-{flag}"


class InputArg(pydantic.BaseModel):
    arg1: Annotated[int, pydantic.Field(..., ge=0, le=1)]
    arg2: str
    kwarg1: Annotated[int, pydantic.Field(..., ge=0, le=1)] = 0
    kwarg2: str = ""


def f5(ctx: JobContext, arg: InputArg) -> str:
    """This is f5."""
    return f"{type(ctx).__name__}-{arg.model_dump_json()}"


def f5_wrong_input_arg_type(ctx: JobContext, arg: int) -> str:
    """This is f5 with 'u' being an int --> raise type error"""
    return f"{type(ctx).__name__}-{arg}"


def f5_too_many_args(ctx: JobContext, u: InputArg, v: float) -> str:
    """This is f5 with 'u' being input arg  --> raise v is illegal"""
    return f"{type(ctx).__name__}-{u.model_dump_json()}-{v}"


# noinspection PyMethodMayBeStatic
class RegisteredProcessTest(BaseModelMixin, TestCase):
    # noinspection PyMethodMayBeStatic
    def test_create_fail(self):
        with pytest.raises(TypeError, match="function argument must be callable"):
            # noinspection PyTypeChecker
            Process.create(42)

    def test_create_f1(self):
        process = Process.create(f1)
        self.assertIsInstance(process, Process)
        self.assertIs(f1, process.function)
        proc_desc = process.description
        self.assertIsInstance(proc_desc, ProcessDescription)
        self.assertEqual("tests.process.test_process:f1", proc_desc.id)
        self.assertEqual("0.0.0", proc_desc.version)
        self.assertEqual(None, proc_desc.title)
        self.assertEqual("This is f1.", proc_desc.description)
        proc_inputs = proc_desc.inputs
        proc_outputs = proc_desc.outputs
        self.assertIsInstance(proc_inputs, dict)
        self.assertIsInstance(proc_outputs, dict)
        self.assertEqual(["x", "y"], list(proc_inputs.keys()))
        self.assertEqual(["return_value"], list(proc_outputs.keys()))
        self.assertBaseModelEqual(
            InputDescription(title="X", schema=Schema(type=DataType.number)),
            proc_inputs["x"],
        )
        self.assertBaseModelEqual(
            InputDescription(title="Y", schema=Schema(type=DataType.number)),
            proc_inputs["y"],
        )
        self.assertEqual(
            OutputDescription(
                title="Return Value",
                schema=Schema(type=DataType.number),
            ),
            proc_outputs["return_value"],
        )

    # noinspection PyMethodMayBeStatic
    def test_create_f1_with_input_fields(self):
        process = Process.create(
            f1,
            input_fields={
                "x": Field(title="A wonderful X", ge=0.0),
                "y": Field(title="A beautiful Y", lt=1.0),
            },
        )
        self.assertIsInstance(process, Process)
        self.assertIs(f1, process.function)
        self.assertEqual(None, process.job_ctx_arg)
        proc_desc = process.description
        proc_inputs = proc_desc.inputs
        proc_outputs = proc_desc.outputs
        self.assertIsInstance(proc_inputs, dict)
        self.assertIsInstance(proc_outputs, dict)
        self.assertEqual(["x", "y"], list(proc_inputs.keys()))
        self.assertEqual(["return_value"], list(proc_outputs.keys()))
        self.assertBaseModelEqual(
            InputDescription(
                title="A wonderful X", schema=Schema(type=DataType.number, minimum=0.0)
            ),
            proc_inputs["x"],
        )
        self.assertBaseModelEqual(
            InputDescription(
                title="A beautiful Y",
                schema=Schema(type=DataType.number, exclusiveMaximum=1.0),
            ),
            proc_inputs["y"],
        )
        self.assertEqual(
            OutputDescription(
                title="Return Value",
                schema=Schema(type=DataType.number),
            ),
            proc_outputs["return_value"],
        )

    def test_create_f2(self):
        process = Process.create(f2)
        self.assertIsInstance(process, Process)
        self.assertIs(f2, process.function)
        self.assertEqual(None, process.job_ctx_arg)
        proc_desc = process.description
        self.assertIsInstance(proc_desc, ProcessDescription)
        self.assertEqual("tests.process.test_process:f2", proc_desc.id)
        self.assertEqual("0.0.0", proc_desc.version)
        self.assertEqual(None, proc_desc.title)
        self.assertEqual("This is f2.", proc_desc.description)
        proc_inputs = proc_desc.inputs
        proc_outputs = proc_desc.outputs
        self.assertIsInstance(proc_inputs, dict)
        self.assertIsInstance(proc_outputs, dict)
        self.assertEqual(["a", "b"], list(proc_inputs.keys()))
        self.assertEqual(["return_value"], list(proc_outputs.keys()))
        self.assertBaseModelEqual(
            InputDescription(
                title="A",
                schema=Schema(type=DataType.boolean, nullable=True),
            ),
            proc_inputs["a"],
        )
        self.assertBaseModelEqual(
            InputDescription(
                title="B",
                schema=Schema(
                    anyOf=[
                        Schema(type=DataType.number),
                        Schema(type=DataType.boolean),
                    ],
                ),
            ),
            proc_inputs["b"],
        )
        self.assertBaseModelEqual(
            OutputDescription(
                title="Return Value",
                schema=Schema(
                    type=DataType.array,
                    items=Schema(type="number"),
                    minItems=2,
                    maxItems=2,
                ),
            ),
            proc_outputs["return_value"],
        )

    def test_create_f2_with_one_output_field(self):
        process = Process.create(
            f2,
            output_fields={
                "point": Field(title="A point (x, y)"),
            },
        )
        self.assertIsInstance(process, Process)
        self.assertIs(f2, process.function)
        proc_desc = process.description
        self.assertIsInstance(proc_desc, ProcessDescription)
        self.assertEqual("tests.process.test_process:f2", proc_desc.id)
        self.assertEqual("0.0.0", proc_desc.version)
        self.assertEqual(None, proc_desc.title)
        self.assertEqual("This is f2.", proc_desc.description)
        proc_inputs = proc_desc.inputs
        proc_outputs = proc_desc.outputs
        self.assertIsInstance(proc_inputs, dict)
        self.assertIsInstance(proc_outputs, dict)
        self.assertEqual(["a", "b"], list(proc_inputs.keys()))
        self.assertEqual(["point"], list(proc_outputs.keys()))
        self.assertBaseModelEqual(
            OutputDescription(
                title="A point (x, y)",
                schema=Schema(
                    type=DataType.array,
                    items=Schema(type="number"),
                    minItems=2,
                    maxItems=2,
                ),
            ),
            proc_outputs["point"],
        )

    def test_create_f2_with_two_output_fields(self):
        process = Process.create(
            f2,
            output_fields={
                "x": Field(title="The X", ge=0.0),
                "y": Field(title="The Y", lt=1.0),
            },
        )
        self.assertIsInstance(process, Process)
        self.assertIs(f2, process.function)
        proc_desc = process.description
        self.assertIsInstance(proc_desc, ProcessDescription)
        self.assertEqual("tests.process.test_process:f2", proc_desc.id)
        self.assertEqual("0.0.0", proc_desc.version)
        self.assertEqual(None, proc_desc.title)
        self.assertEqual("This is f2.", proc_desc.description)
        proc_inputs = proc_desc.inputs
        proc_outputs = proc_desc.outputs
        self.assertIsInstance(proc_inputs, dict)
        self.assertIsInstance(proc_outputs, dict)
        self.assertEqual(["a", "b"], list(proc_inputs.keys()))
        self.assertEqual(["x", "y"], list(proc_outputs.keys()))
        self.assertBaseModelEqual(
            OutputDescription(
                title="The X",
                schema=Schema(type=DataType.number, minimum=0.0),
            ),
            proc_outputs["x"],
        )
        self.assertEqual(
            OutputDescription(
                title="The Y",
                schema=Schema(type=DataType.number, exclusiveMaximum=1.0),
            ),
            proc_outputs["y"],
        )

    # noinspection PyMethodMayBeStatic
    def test_create_with_illegal_f1_with_output_fields(self):
        with pytest.raises(
            TypeError,
            match=(
                r"function 'tests\.process\.test_process:f1': "
                r"return type must be tuple\[\] with arguments"
            ),
        ):
            Process.create(
                f1,
                output_fields={
                    "x": Field(title="The X", ge=0.0),
                    "y": Field(title="The Y", lt=1.0),
                },
            )

    # noinspection PyMethodMayBeStatic
    def test_create_f1_with_illegal_input_fields(self):
        with pytest.raises(
            ValueError,
            match=(
                r"function 'tests\.process\.test_process:f1': "
                r"all input names must have corresponding parameter names; "
                r"invalid input name\(s\)\: 'u', 'v'"
            ),
        ):
            Process.create(
                f1,
                input_fields={
                    "x": Field(title="The valid X", ge=0.0),
                    "y": Field(title="The valid Y", lt=1.0),
                    "u": Field(title="The illegal U"),
                    "v": Field(title="The illegal V"),
                },
            )

    # noinspection PyMethodMayBeStatic
    def test_create_f2_with_illegal_output_fields(self):
        with pytest.raises(
            ValueError,
            match=(
                r"function 'tests\.process\.test_process:f2': "
                r"number of outputs must match number of tuple\[\] arguments"
            ),
        ):
            Process.create(
                f2,
                output_fields={
                    "x": Field(title="The X", ge=0.0),
                    "y": Field(title="The Y", lt=1.0),
                    "z": Field(title="The Z"),
                },
            )

    def test_create_f1_with_props(self):
        process = Process.create(f1, id="foo", version="1.0.2", title="My Foo")
        self.assertIsInstance(process, Process)
        self.assertIs(f1, process.function)
        process_desc = process.description
        self.assertIsInstance(process_desc, ProcessDescription)
        self.assertEqual("foo", process_desc.id)
        self.assertEqual("1.0.2", process_desc.version)
        self.assertEqual("My Foo", process_desc.title)
        self.assertEqual("This is f1.", process_desc.description)
        self.assertIsInstance(process_desc.inputs, dict)
        self.assertIsInstance(process_desc.outputs, dict)

    def test_create_f3(self):
        process = Process.create(f3, id="f3")
        self.assertIsInstance(process, Process)
        self.assertEqual(None, process.job_ctx_arg)
        self.assertEqual(
            {"point1", "point2"},
            set(process.description.inputs.keys()),
        )
        self.assertBaseModelEqual(
            InputDescription(
                title="Point",
                description="A 2-D point.",
                schema=Schema(
                    **{
                        "type": "object",
                        "properties": {
                            "x": {
                                "type": "number",
                                "default": 0.0,
                                "title": "X-coordinate",
                            },
                            "y": {
                                "type": "number",
                                "default": 0.0,
                                "title": "Y-coordinate",
                            },
                        },
                    }
                ),
            ),
            process.description.inputs["point1"],
        )

    def test_create_f4(self):
        process = Process.create(f4, id="f4")
        self.assertIsInstance(process, Process)
        self.assertIs(f4, process.function)
        self.assertEqual("ctx", process.job_ctx_arg)

    def test_create_f4_fail_ctx(self):
        with pytest.raises(
            ValueError,
            match="function '.*:f4_fail_ctx': only one parameter "
            "can have type JobContext, but found 'ctx' and 'ctx2'",
        ):
            Process.create(f4_fail_ctx, id="f4_fail_ctx")

    def test_create_f5(self):
        def assert_process_ok(p: Process):
            self.assertIsInstance(p, Process)
            self.assertIs(f5, p.function)
            self.assertEqual("ctx", p.job_ctx_arg)
            self.assertIsInstance(p.description, ProcessDescription)
            self.assertIsInstance(p.description.inputs, dict)
            return p.description.inputs

        def assert_input_arg_expanded(p: Process):
            inputs = assert_process_ok(p)
            self.assertEqual(["arg1", "arg2", "kwarg1", "kwarg2"], list(inputs.keys()))
            self.assertTrue(
                all(map(lambda v: isinstance(v, InputDescription), inputs.values()))
            )

        def assert_input_arg_untouched(p: Process):
            inputs = assert_process_ok(p)
            self.assertEqual(["arg"], list(inputs.keys()))
            self.assertTrue(
                all(map(lambda v: isinstance(v, InputDescription), inputs.values()))
            )

        process = Process.create(f5, id="f5", inputs_arg="arg")
        assert_input_arg_expanded(process)

        process = Process.create(f5, id="f5", inputs_arg=True)
        assert_input_arg_expanded(process)

        process = Process.create(f5, id="f5", inputs_arg=False)
        assert_input_arg_untouched(process)

    def test_create_f5_with_wrong_input_arg(self):
        with pytest.raises(
            ValueError,
            match="function '.*:f5': specified inputs argument is not an "
            "argument of the function \(inputs_arg='x'\)",
        ):
            Process.create(f5, id="f5", inputs_arg="x")

    def test_create_f5_wrong_input_arg_type(self):
        with pytest.raises(
            TypeError,
            match="function '.*:f5_wrong_input_arg_type': "
            "type of inputs argument 'arg' must be a subclass "
            "of pydantic.BaseModel",
        ):
            Process.create(
                f5_wrong_input_arg_type, id="f5_wrong_input_arg_type", inputs_arg="arg"
            )

    def test_create_f5_too_many_args(self):
        with pytest.raises(
            ValueError,
            match="function '.*:f5_too_many_args': the inputs argument must "
            "be the only argument \(inputs_arg='u'\)",
        ):
            Process.create(f5_too_many_args, id="f5_too_many_args", inputs_arg="u")
