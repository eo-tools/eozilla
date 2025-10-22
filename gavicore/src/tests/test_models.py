#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from enum import Enum
from unittest import TestCase

from pydantic import BaseModel

import s2gos_common.models as s2g_models

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
            for name, obj in inspect.getmembers(s2g_models, inspect.isclass)
            if issubclass(obj, Enum)
        )
        self.assertSetIsOk(REQUIRED_ENUMS, all_enums)

    def test_classes(self):
        all_classes = set(
            name
            for name, obj in inspect.getmembers(s2g_models, inspect.isclass)
            if issubclass(obj, BaseModel)
        )
        self.assertSetIsOk(REQUIRED_CLASSES, all_classes)

    def assertSetIsOk(self, required: set[str], actual: set[str]):
        contained_items = set(c for c in required if c in actual)
        self.assertSetEqual(required, contained_items, "contained")

    def test_models_have_repr_json(self):
        for name, obj in inspect.getmembers(s2g_models, inspect.isclass):
            if name in REQUIRED_CLASSES and issubclass(obj, BaseModel):
                self.assertTrue(hasattr(obj, "_repr_json_"), msg=f"model {name}")

        obj = s2g_models.Bbox(bbox=[10, 20, 30, 40])
        json_repr = obj._repr_json_()
        self.assertEqual(
            (
                {"bbox": [10.0, 20.0, 30.0, 40.0]},
                {"root": "Bbox object:"},
            ),
            json_repr,
        )
