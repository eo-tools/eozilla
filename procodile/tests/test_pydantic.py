#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Annotated
from unittest import TestCase

import pydantic
import pytest


# noinspection PyMethodMayBeStatic
class PydanticTest(TestCase):
    """
    This test case ensures that pydantic behaves as expected
    by own code in this package
    """

    def test_that_field_names_dont_need_to_be_python_identifiers(self):
        model_class: type[pydantic.BaseModel] = pydantic.create_model(
            "Pippo", **{"sur-name": str, "max.age": int}
        )
        self.assertIsInstance(model_class, type)
        self.assertTrue(issubclass(model_class, pydantic.BaseModel))
        self.assertEqual({"sur-name", "max.age"}, set(model_class.model_fields.keys()))

        # noinspection PyArgumentList
        model_instance = model_class(**{"sur-name": "Bibo", "max.age": 100})
        self.assertEqual(
            {"max.age": 100, "sur-name": "Bibo"}, model_instance.model_dump(mode="json")
        )

    def test_that_extra_fields_are_rejected(self):
        class NoExtrasModel(pydantic.BaseModel):
            some_data: int
            model_config = {"extra": "forbid"}

        with pytest.raises(pydantic.ValidationError):
            # noinspection PyArgumentList
            NoExtrasModel(some_data=1, unexpected="nope")

    def test_that_model_json_schema_converts_limits(self):
        class MyModel(pydantic.BaseModel):
            x: Annotated[float, pydantic.Field(ge=-1.5, le=1.5)]
            y: Annotated[float, pydantic.Field(gt=0.0, lt=1.0)]

        schema = MyModel.model_json_schema()
        assert schema == {
            "type": "object",
            "title": "MyModel",
            "required": ["x", "y"],
            "properties": {
                "x": {
                    "maximum": 1.5,
                    "minimum": -1.5,
                    "title": "X",
                    "type": "number",
                },
                "y": {
                    "exclusiveMaximum": 1.0,
                    "exclusiveMinimum": 0.0,
                    "title": "Y",
                    "type": "number",
                },
            },
        }
