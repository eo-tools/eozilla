#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from typing import TypeVar
from unittest import TestCase

from pydantic import BaseModel

import gavicore.dru_models as m

REQUIRED_CLASSES = {
    "OGCApplicationPackage",
    "OGCApplicationPackageProcessDescription",
    "CWLDescription",
    "ContainerImage",
    "ExecutionUnitContainer",
    "ContainerConfig",
    "ContainerBindings",
    "InputBinding",
    "OutputBinding",
    "GenericExecutionUnit",
}

T = TypeVar("T", bound=BaseModel)


class DRUModelsTest(TestCase):
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
