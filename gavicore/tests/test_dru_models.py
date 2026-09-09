#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import inspect
from typing import Any, TypeVar
from unittest import TestCase

from pydantic import BaseModel

import gavicore.dru_models as m

REQUIRED_CLASSES = {
    "OgcApplicationPackage",
    "OgcApplicationPackageProcessDescription",
    "CwlDescription",
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

    def test_models_with_extensions(self):
        execution_unit_container = self._assert_extendable_model(
            m.ExecutionUnitContainer,
            {
                "image": "ghcr.io/osgeo/gdal:alpine-normal-latest-amd64",
                "x-placeholder": ["list", "of", "extra", "values"],
            },
        )
        self.assertEqual(
            ["list", "of", "extra", "values"],
            execution_unit_container.model_extra.get("x-placeholder"),
        )

        container_config = self._assert_extendable_model(
            m.ContainerConfig, {"x-placeholder": {"gpu_config": {"vendor": "nvidia"}}}
        )
        self.assertEqual(
            {"gpu_config": {"vendor": "nvidia"}},
            container_config.model_extra.get("x-placeholder"),
        )

        input_binding = self._assert_extendable_model(
            m.InputBinding, {"x-placeholder": "literal value"}
        )
        self.assertEqual(
            "literal value", input_binding.model_extra.get("x-placeholder")
        )

        output_binding = self._assert_extendable_model(
            m.OutputBinding, {"x-placeholder": 13}
        )
        self.assertEqual(13, output_binding.model_extra.get("x-placeholder"))

    def _assert_extendable_model(self, model_cls: type[T], data: dict[str, Any]) -> T:
        model_instance = model_cls(**data)
        self.assertEqual(
            data,
            model_instance.model_dump(mode="json", by_alias=True, exclude_unset=True),
        )
        return model_instance
