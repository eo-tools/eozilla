#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pydantic


class PydanticTest(TestCase):
    """
    This test case ensures that pydantic behaves as expected
    by own code in this package
    """

    def test_field_names_dont_need_to_be_python_identifiers(self):
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
