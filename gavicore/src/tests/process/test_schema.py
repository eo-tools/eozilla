#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated
from unittest import TestCase

import pydantic
import pytest

from s2gos_common.models import Schema
from s2gos_common.process.schema import (
    create_schema_instance,
    inline_schema_refs,
)


class SchemaTest(TestCase):
    def test_pydantic_model_json_schema(self):
        class MyModel(pydantic.BaseModel):
            x: Annotated[float, pydantic.Field(ge=-1.5, le=1.5)]
            y: Annotated[float, pydantic.Field(gt=0.0, lt=1.0)]

        schema = MyModel.model_json_schema()
        self.assertEqual(
            {
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
            },
            schema,
        )

    def test_create_schema_instance(self):
        self.assertEqual(
            Schema(type="number"),
            create_schema_instance("x", {"type": "number"}),
        )

        with pytest.raises(pydantic.ValidationError):
            create_schema_instance("x", {"tüp": "number"})

    def test_inline_schema_refs(self):
        schema = inline_schema_refs(
            {
                "type": "array",
                "items": {"$ref": "#/$defs/Line"},
                "$defs": {
                    "Line": {
                        "type": "object",
                        "properties": {
                            "p1": {"$ref": "#/$defs/Point"},
                            "p2": {"$ref": "#/$defs/Point"},
                        },
                        "required": ["p1", "p2"],
                    },
                    "Point": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                        },
                        "required": ["x", "y"],
                    },
                },
            }
        )
        self.assertEqual(
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["p1", "p2"],
                    "properties": {
                        "p1": {
                            "type": "object",
                            "required": ["x", "y"],
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                        },
                        "p2": {
                            "type": "object",
                            "required": ["x", "y"],
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                        },
                    },
                },
            },
            schema,
        )
