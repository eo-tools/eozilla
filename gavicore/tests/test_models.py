#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from enum import Enum
from typing import Any, TypeVar
from unittest import TestCase

from pydantic import BaseModel, ValidationError

import gavicore.models as m


class CustomValueError(ValueError):
    pass


class CustomException(Exception):
    pass


REQUIRED_ENUMS = {
    "CRS",
    "DataType",
    "JobControlOptions",
    "JobStatus",
}

REQUIRED_CLASSES = {
    "ApiError",
    "Capabilities",
    "ConformanceDeclaration",
    "Format",
    "InputDescription",
    "JobInfo",
    "JobList",
    "Link",
    "Metadata",
    "Output",
    "OutputDescription",
    "ProcessDescription",
    "ProcessList",
    "ProcessRequest",
    "ProcessSummary",
    "Schema",
}

T = TypeVar("T", bound=BaseModel)


class ModelsTest(TestCase):
    def test_enums(self):
        all_enums = set(
            name
            for name, obj in inspect.getmembers(m, inspect.isclass)
            if issubclass(obj, Enum)
        )
        self.assertSetIsOk(REQUIRED_ENUMS, all_enums)

    def test_classes(self):
        all_classes = set(
            name
            for name, obj in inspect.getmembers(m, inspect.isclass)
            if issubclass(obj, BaseModel)
        )
        self.assertSetIsOk(REQUIRED_CLASSES, all_classes)

    def assertSetIsOk(self, required: set[str], actual: set[str]):
        contained_items = set(c for c in required if c in actual)
        self.assertSetEqual(required, contained_items, "contained")

    def test_models_have_repr_json(self):
        for name, obj in inspect.getmembers(m, inspect.isclass):
            if name in REQUIRED_CLASSES and issubclass(obj, BaseModel):
                self.assertTrue(hasattr(obj, "_repr_json_"), msg=f"model {name}")

        obj = m.Bbox(bbox=[10, 20, 30, 40])
        # noinspection PyUnresolvedReferences
        json_repr = obj._repr_json_()
        self.assertEqual(
            (
                {"bbox": [10.0, 20.0, 30.0, 40.0]},
                {"root": "Bbox object:"},
            ),
            json_repr,
        )

    def test_models_with_extensions(self):
        api_error = self._assert_extendable_model(
            m.ApiError,
            {
                "title": "Key not found",
                "status": 500,
                "type": "KeyError",
                "x-traceback": ["hello", "world"],
            },
        )
        self.assertEqual(["hello", "world"], api_error.traceback)

        job_info = self._assert_extendable_model(
            m.JobInfo,
            {
                "type": "process",
                "jobID": "job_1",
                "status": "failed",
                "x-traceback": "hello\nworld",
            },
        )
        self.assertEqual("hello\nworld", job_info.traceback)

        input_description = self._assert_extendable_model(
            m.InputDescription,
            {
                "title": "Threshold",
                "schema": {"type": "number"},
                "x-ui": {"widget": "slider"},
            },
        )
        self.assertEqual(
            {"widget": "slider"}, input_description.model_extra.get("x-ui")
        )

        output_description = self._assert_extendable_model(
            m.OutputDescription,
            {
                "title": "Output URL",
                "schema": {"type": "string", "format": "uri"},
                "x-ui": {"widget": "text"},
            },
        )
        self.assertEqual({"widget": "text"}, output_description.model_extra.get("x-ui"))

    def test_api_error_closest_builtin_exc(self):
        self.assertIs(m.ApiError._closest_builtin_exc(CustomValueError), ValueError)
        self.assertIs(m.ApiError._closest_builtin_exc(CustomException), Exception)

    def test_api_error_create_without_exception(self):
        api_error = m.ApiError.create(
            type_uri="https://example.com/probs/invalid-request",
            title="Invalid request",
            status=400,
            detail="Missing required field.",
            instance="/requests/123",
        )

        self.assertEqual(
            m.ApiError(
                type="https://example.com/probs/invalid-request",
                title="Invalid request",
                status=400,
                detail="Missing required field.",
                instance="/requests/123",
            ),
            api_error,
        )

    def test_api_error_create_from_builtin_exception(self):
        try:
            raise RuntimeError("Boom")
        except RuntimeError as exc:
            runtime_error = exc

        api_error = m.ApiError.create(
            exc=runtime_error,
            status=500,
            detail="The request failed.",
            instance="/jobs/42",
        )

        self.assertEqual(
            "https://docs.python.org/3/library/exceptions.html#RuntimeError",
            api_error.type,
        )
        self.assertEqual("Boom", api_error.title)
        self.assertEqual(500, api_error.status)
        self.assertEqual("The request failed.", api_error.detail)
        self.assertEqual("/jobs/42", api_error.instance)
        self.assertIsInstance(api_error.traceback, list)
        self.assertTrue(api_error.traceback)

    def test_api_error_create_from_validation_error(self):
        class Payload(BaseModel):
            count: int

        try:
            # noinspection PyTypeChecker
            Payload(count="not an int")
        except ValidationError as exc:
            validation_error = exc

        # noinspection PyUnboundLocalVariable
        api_error = m.ApiError.create(exc=validation_error, status=422)

        self.assertEqual(m.ApiError.VALIDATION_ERROR_URI, api_error.type)
        self.assertEqual(str(validation_error), api_error.title)
        self.assertEqual(422, api_error.status)
        self.assertIsInstance(api_error.traceback, list)
        self.assertTrue(api_error.traceback)

    def _assert_extendable_model(self, model_cls: type[T], data: dict[str, Any]) -> T:
        model_instance = model_cls(**data)
        self.assertEqual(
            data,
            model_instance.model_dump(mode="json", by_alias=True, exclude_unset=True),
        )
        return model_instance
