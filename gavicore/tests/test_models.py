#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from enum import Enum
from unittest import TestCase

from pydantic import BaseModel

import gavicore.models as m

REQUIRED_ENUMS = {
    "CRS",
    "DataType",
    "MaxOccurs",
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
        error = m.ApiError(
            **{
                "title": "Key not found",
                "status": 500,
                "type": "KeyError",
                "x-traceback": ["hello", "world"],
            },
        )
        self.assertEqual(
            {
                "title": "Key not found",
                "status": 500,
                "type": "KeyError",
                "x-traceback": ["hello", "world"],
            },
            error.model_dump(mode="json", by_alias=True, exclude_unset=True),
        )
        self.assertEqual(["hello", "world"], error.traceback)

        job_info = m.JobInfo(
            **{
                "type": "process",
                "jobID": "job_1",
                "status": "failed",
                "x-traceback": "hello\nworld",
            },
        )
        self.assertEqual(
            {
                "type": "process",
                "jobID": "job_1",
                "status": "failed",
                "x-traceback": "hello\nworld",
            },
            job_info.model_dump(mode="json", by_alias=True, exclude_unset=True),
        )
        self.assertEqual("hello\nworld", job_info.traceback)

        input_description = m.InputDescription(
            **{
                "title": "Threshold",
                "schema": {"type": "number"},
                "x-ui": {"widget": "slider"},
            }
        )
        self.assertEqual(
            {
                "title": "Threshold",
                "schema": {"type": "number"},
                "x-ui": {"widget": "slider"},
            },
            input_description.model_dump(
                mode="json", by_alias=True, exclude_unset=True
            ),
        )
        self.assertEqual(
            {"widget": "slider"}, input_description.model_extra.get("x-ui")
        )
