#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated
from unittest import TestCase

import pydantic

from procodile.schema import (
    inline_schema_refs,
    json_schema_to_openapi_schema,
    model_class_to_openapi_schema_dict,
)


class SimpleModel(pydantic.BaseModel):
    name: Annotated[str, pydantic.Field(min_length=1)]
    threshold: Annotated[int | float | None, pydantic.Field(gt=0.0, lt=1.0)] = 0.5


class HeterogeneousTupleModel(pydantic.BaseModel):
    name: str
    address: tuple[str, int, bool]


class HomogeneousTupleModel(pydantic.BaseModel):
    name: str
    bbox: tuple[float, float, float, float]


class NoExtrasModel(pydantic.BaseModel):
    some_data: int
    model_config = {"extra": "forbid"}


# noinspection PyMethodMayBeStatic
class ModelClassToOpenapiSchemaDictTest(TestCase):
    def test_simple_model(self):
        # noinspection PyArgumentList
        schema = model_class_to_openapi_schema_dict(SimpleModel)

        assert schema == {
            "type": "object",
            "title": "SimpleModel",
            "properties": {
                "name": {
                    "type": "string",
                    "title": "Name",
                    "minLength": 1,
                },
                "threshold": {
                    "anyOf": [{"type": "integer"}, {"type": "number"}],
                    "default": 0.5,
                    "gt": 0.0,
                    "lt": 1.0,
                    "nullable": True,
                    "title": "Threshold",
                },
            },
            "required": ["name"],
        }

    def test_heterogeneous_tuple_model(self):
        # noinspection PyArgumentList
        schema = model_class_to_openapi_schema_dict(HeterogeneousTupleModel)

        assert schema == {
            "type": "object",
            "title": "HeterogeneousTupleModel",
            "properties": {
                "name": {
                    "title": "Name",
                    "type": "string",
                },
                "address": {
                    "type": "array",
                    "title": "Address",
                    "items": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "integer"},
                            {"type": "boolean"},
                        ]
                    },
                    "maxItems": 3,
                    "minItems": 3,
                },
            },
            "required": ["name", "address"],
        }

    def test_homogeneous_tuple_model(self):
        # noinspection PyArgumentList
        schema = model_class_to_openapi_schema_dict(HomogeneousTupleModel)

        assert schema == {
            "type": "object",
            "title": "HomogeneousTupleModel",
            "properties": {
                "name": {
                    "title": "Name",
                    "type": "string",
                },
                "bbox": {
                    "type": "array",
                    "title": "Bbox",
                    "items": {"type": "number"},
                    "maxItems": 4,
                    "minItems": 4,
                },
            },
            "required": ["name", "bbox"],
        }


# noinspection PyMethodMayBeStatic
class InlineSchemaRefsTest(TestCase):
    point_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
        },
        "required": ["x", "y"],
    }

    defs = {
        "Line": {
            "type": "object",
            "properties": {
                "p1": {"$ref": "#/$defs/Point"},
                "p2": {"$ref": "#/$defs/Point"},
            },
            "required": ["p1", "p2"],
        },
        "Point": point_schema,
    }

    def test_array(self):
        schema = inline_schema_refs(
            {
                "type": "array",
                "items": {"$ref": "#/$defs/Line"},
                "$defs": self.defs,
            }
        )
        assert schema == {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["p1", "p2"],
                "properties": {
                    "p1": self.point_schema,
                    "p2": self.point_schema,
                },
            },
        }

    def test_tuple(self):
        # Note, this test is actually not required for OpenAPI 3.0 as
        # tuples are supported only for versions >= 3.1
        schema = inline_schema_refs(
            {
                "type": "array",
                "items": [{"$ref": "#/$defs/Point"}, {"$ref": "#/$defs/Line"}],
                "$defs": self.defs,
            }
        )
        assert schema == {
            "type": "array",
            "items": [
                self.point_schema,
                {
                    "type": "object",
                    "required": ["p1", "p2"],
                    "properties": {
                        "p1": self.point_schema,
                        "p2": self.point_schema,
                    },
                },
            ],
        }

    def test_any_of(self):
        schema = inline_schema_refs(
            {
                "anyOf": [
                    {"$ref": "#/$defs/Point"},
                    {"$ref": "#/$defs/Line"},
                ],
                "$defs": self.defs,
            }
        )
        assert schema == {
            "anyOf": [
                self.point_schema,
                {
                    "type": "object",
                    "properties": {
                        "p1": self.point_schema,
                        "p2": self.point_schema,
                    },
                    "required": ["p1", "p2"],
                },
            ]
        }

    def test_preserves_boolean_nodes(self):
        # Ensure non-dict schemas (e.g., additionalProperties: false) are left intact
        schema = inline_schema_refs(
            {
                "type": "object",
                "additionalProperties": False,
                "$defs": {"Dummy": {"type": "string"}},
            }
        )
        assert schema["additionalProperties"] is False

    # noinspection PyTypeChecker
    def test_passes_through_non_dict(self):
        assert inline_schema_refs(False) is False
        assert inline_schema_refs(1) == 1

    def test_handles_additional_properties_false(self):
        # Should not crash when additionalProperties is a boolean
        # (forced by extra="forbid")
        schema = inline_schema_refs(NoExtrasModel.model_json_schema())
        assert schema.get("additionalProperties") is False
        assert schema["required"] == ["some_data"]
        assert "properties" in schema and "some_data" in schema["properties"]


# noinspection PyMethodMayBeStatic
class JsonSchemaToOpenapiSchemaTest(TestCase):
    """Test some edge cases."""

    def test_items(self):
        assert json_schema_to_openapi_schema({"items": []}) == {"items": {}}

    def test_prefix_items(self):
        assert json_schema_to_openapi_schema({"prefixItems": []}) == {"items": {}}

    def test_additional_properties(self):
        assert json_schema_to_openapi_schema({"additionalProperties": True}) == {
            "additionalProperties": {}
        }
        assert json_schema_to_openapi_schema({"additionalProperties": None}) == {
            "additionalProperties": {}
        }
        assert json_schema_to_openapi_schema({"additionalProperties": False}) == {
            "additionalProperties": False
        }
        assert json_schema_to_openapi_schema(
            {"additionalProperties": {"type": "string"}}
        ) == {"additionalProperties": {"type": "string"}}
