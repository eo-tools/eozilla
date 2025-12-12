#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated

import pydantic
import pytest

from gavicore.models import Schema
from gavicore.util.schema import (
    create_schema_dict,
    inline_schema_refs,
)


def test_pydantic_model_json_schema():
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


def test_create_schema_dict():
    class MyModel(pydantic.BaseModel):
        name: Annotated[str, pydantic.Field(min_length=1)]
        threshold: Annotated[int | float | None, pydantic.Field(gt=0.0, lt=1.0)] = 0.5

    # noinspection PyArgumentList
    schema = create_schema_dict(MyModel)

    assert schema == {
        "type": "object",
        "title": "MyModel",
        "properties": {
            "name": {
                "minLength": 1,
                "title": "Name",
                "type": "string",
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


def test_inline_schema_refs():
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
    assert schema == {
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
    }


class TestExtraForbidModel:
    class SomeTestClass(pydantic.BaseModel):
        some_data: int
        model_config = {"extra": "forbid"}

    def test_extra_fields_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            self.SomeTestClass(some_data=1, unexpected="nope")

    def test_inline_schema_refs_handles_additional_properties_false(self):
        # Should not crash when additionalProperties is a boolean (extra="forbid")
        schema = inline_schema_refs(self.SomeTestClass.model_json_schema())
        assert schema.get("additionalProperties") is False
        assert schema["required"] == ["some_data"]
        assert "properties" in schema and "some_data" in schema["properties"]


def test_inline_schema_refs_preserves_boolean_nodes():
    # Ensure non-dict schemas (e.g., additionalProperties: false) are left intact
    schema = inline_schema_refs(
        {
            "type": "object",
            "additionalProperties": False,
            "$defs": {"Dummy": {"type": "string"}},
        }
    )
    assert schema["additionalProperties"] is False
