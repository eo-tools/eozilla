#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Any
from unittest import TestCase

import pydantic
from pydantic import BaseModel

from gavicore.models import InputDescription, Schema
from gavicore.ui import FieldMeta
from gavicore.ui.field.meta import FieldGroup

dict_kwargs = dict(
    exclude_none=True, exclude_defaults=True, exclude_unset=True, by_alias=True
)


def to_json(model: BaseModel, exclude: set[str] | None = None):
    return model.model_dump(
        mode="json",
        exclude=exclude,
        exclude_none=True,
        exclude_defaults=True,
        exclude_unset=True,
        by_alias=True,
    )


class FieldMetaTest(TestCase):
    def test_from_input_description(self):
        meta = FieldMeta.from_input_description(
            "threshold",
            InputDescription(
                **{
                    "schema": {"type": "number", "default": 0.5},
                    "minOccurs": 1,
                    "maxOccurs": 1,
                }
            ),
        )
        self.maxDiff = None
        self.assertIsInstance(meta, FieldMeta)
        self.assertEqual(
            {
                "name": "threshold",
                "schema": {
                    "type": "number",
                    "default": 0.5,
                    "title": "Threshold",
                },
                "required": True,
                "title": "Threshold",
            },
            to_json(meta),
        )

    def test_from_input_descriptions(self):
        meta = FieldMeta.from_input_descriptions(
            {
                "datasets": InputDescription(
                    **{
                        "schema": {
                            "type": "string",
                            "format": "uri",
                            "title": "Input dataset",
                        },
                        "minOccurs": 1,
                        "maxOccurs": "unbounded",
                    }
                ),
                "threshold": InputDescription(
                    **{
                        "schema": {"type": "number", "default": 0.5},
                        "minOccurs": 0,
                        "maxOccurs": 1,
                    }
                ),
                "boost": InputDescription(
                    **{"schema": {"type": "boolean"}, "title": "Use fast path"}
                ),
            }
        )
        self.maxDiff = None
        self.assertIsInstance(meta, FieldMeta)

        schema_1 = {
            "type": "string",
            "format": "uri",
            "title": "Input dataset",
        }
        schema_2 = {
            "type": "number",
            "default": 0.5,
            "title": "Threshold",
        }
        schema_3 = {"type": "boolean", "title": "Use fast path"}
        self.assertEqual(
            {
                "name": "inputs",
                "properties": {
                    "datasets": {
                        "name": "datasets",
                        "schema": {
                            "items": schema_1,
                            "minItems": 1,
                            "title": "Datasets",
                            "type": "array",
                        },
                        "required": True,
                        "items": {
                            "name": "datasets_item",
                            "required": True,
                            "schema": schema_1,
                            "title": "Input dataset",
                        },
                        "title": "Datasets",
                    },
                    "threshold": {
                        "name": "threshold",
                        "schema": schema_2,
                        "required": False,
                        "title": "Threshold",
                    },
                    "boost": {
                        "name": "boost",
                        "schema": schema_3,
                        "required": True,
                        "title": "Use fast path",
                    },
                },
                "required": True,
                "schema": {
                    "properties": {
                        "boost": schema_3,
                        "datasets": {
                            "items": schema_1,
                            "minItems": 1,
                            "title": "Datasets",
                            "type": "array",
                        },
                        "threshold": schema_2,
                    },
                    "required": ["datasets", "boost"],
                    "title": "Inputs",
                    "type": "object",
                },
                "title": "Inputs",
            },
            to_json(meta),
        )

    def test_object_schema(self):
        schema_prop_1 = Schema(
            **{"type": "number", "title": "Threshold", "x-ui": {"widget": "slider"}}
        )
        schema_prop_2 = Schema(
            **{"type": "boolean", "title": "Boost", "x-ui": {"widget": "switch"}}
        )
        schema = Schema(
            **{
                "type": "object",
                "properties": {
                    "threshold": schema_prop_1,
                    "boost": schema_prop_2,
                },
                "required": ["threshold"],
            }
        )
        meta = FieldMeta.from_schema("performance", schema)
        schema_1 = {
            "title": "Threshold",
            "type": "number",
            "x-ui": {"widget": "slider"},
        }
        schema_2 = {
            "title": "Boost",
            "type": "boolean",
            "x-ui": {"widget": "switch"},
        }
        self.assertEqual(
            {
                "name": "performance",
                "schema": {
                    "type": "object",
                    "required": ["threshold"],
                    "properties": {
                        "threshold": schema_1,
                        "boost": schema_2,
                    },
                },
                "properties": {
                    "threshold": {
                        "name": "threshold",
                        "required": True,
                        "schema": schema_1,
                        "title": "Threshold",
                        "widget": "slider",
                    },
                    "boost": {
                        "name": "boost",
                        "required": False,
                        "schema": schema_2,
                        "title": "Boost",
                        "widget": "switch",
                    },
                },
            },
            to_json(meta),
        )

    def test_object_schema_with_layout(self):
        meta = FieldMeta.from_schema(
            "root",
            Schema(
                **{
                    "type": "object",
                    "x-ui:layout": {
                        "type": "row",
                        "items": [
                            "ds_paths",
                            {
                                "type": "column",
                                "items": ["config_path", "threshold", "verbose"],
                            },
                        ],
                    },
                    "properties": {
                        "ds_paths": {
                            "type": "array",
                            "items": {"type": "string", "format": "uri"},
                        },
                        "config_path": {
                            "type": "string",
                            "format": "uri",
                        },
                        "threshold": {
                            "type": "number",
                            "nullable": True,
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.5,
                        },
                        "verbose": {"type": "boolean"},
                    },
                }
            ),
        )
        self.assertIsInstance(meta, FieldMeta)
        self.assertIsInstance(meta.layout, FieldGroup)
        self.assertEqual(
            FieldGroup(
                type="row",
                items=[
                    "ds_paths",
                    FieldGroup(
                        type="column",
                        items=["config_path", "threshold", "verbose"],
                    ),
                ],
            ),
            meta.layout,
        )

    def test_input_precedence(self):
        self._assert_description(
            description_props={
                "title": "The threshold D.1",
                "x-ui": {"title": "The threshold D.2"},
                "x-ui:title": "The threshold D.3",
            },
            schema_props={
                "title": "The threshold S.1",
                "x-ui": {"title": "The threshold S.2"},
                "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "The threshold D.3"},
        )

        self._assert_description(
            description_props={
                "title": "The threshold D.1",
                "x-ui": {"title": "The threshold D.2"},
                # "x-ui:title": "The threshold D.3",
            },
            schema_props={
                "title": "The threshold S.1",
                "x-ui": {"title": "The threshold S.2"},
                "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "The threshold S.3"},
        )

        self._assert_description(
            description_props={
                "title": "The threshold D.1",
                "x-ui": {"title": "The threshold D.2"},
                # "x-ui:title": "The threshold D.3",
            },
            schema_props={
                "title": "The threshold S.1",
                "x-ui": {"title": "The threshold S.2"},
                # "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "The threshold D.2"},
        )

        self._assert_description(
            description_props={
                "title": "The threshold D.1",
                # "x-ui": {"title": "The threshold D.2"},
                # "x-ui:title": "The threshold D.3",
            },
            schema_props={
                "title": "The threshold S.1",
                "x-ui": {"title": "The threshold S.2"},
                # "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "The threshold S.2"},
        )

        self._assert_description(
            description_props={
                "title": "The threshold D.1",
                # "x-ui": {"title": "The threshold D.2"},
                # "x-ui:title": "The threshold D.3",
            },
            schema_props={
                "title": "The threshold S.1",
                # "x-ui": {"title": "The threshold S.2"},
                # "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "The threshold D.1"},
        )

        self._assert_description(
            description_props={
                # "title": "The threshold D.1",
                # "x-ui": {"title": "The threshold D.2"},
                # "x-ui:title": "The threshold D.3",
            },
            schema_props={
                "title": "The threshold S.1",
                # "x-ui": {"title": "The threshold S.2"},
                # "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "The threshold S.1"},
        )

        self._assert_description(
            description_props={
                # "title": "The threshold D.1",
                # "x-ui": {"title": "The threshold D.2"},
                # "x-ui:title": "The threshold D.3",
            },
            schema_props={
                # "title": "The threshold S.1",
                # "x-ui": {"title": "The threshold S.2"},
                # "x-ui:title": "The threshold S.3",
            },
            expected_props={"title": "Threshold"},
        )

    def _assert_description(
        self,
        description_props: dict[str, Any],
        schema_props: dict[str, Any],
        expected_props: dict[str, Any],
    ):
        kwargs = {**description_props, "schema": schema_props}
        meta = FieldMeta.from_input_descriptions(
            {"threshold": InputDescription(**kwargs)}
        )

        properties = meta.properties
        self.assertIsInstance(properties, dict)
        self.assertEqual(1, len(properties))
        self.assertEqual(
            {
                "name": "threshold",
                **expected_props,
            },
            to_json(properties.get("threshold"), exclude={"schema_", "required"}),
        )

    def test_label(self):
        meta = FieldMeta.from_schema("max_bias", Schema(**{"type": "number"}))
        self.assertEqual("Max Bias", meta.label)
        meta = FieldMeta.from_schema(
            "max_bias", Schema(**{"type": "number", "title": "Maximum bias"})
        )
        self.assertEqual("Maximum bias", meta.label)
        meta = FieldMeta.from_schema(
            "max_bias", Schema(**{"type": "number", "title": ""})
        )
        self.assertEqual("", meta.label)

    def test_cannot_override_properties_with_wrong_type(self):
        meta = FieldMeta.from_schema(
            "x", Schema(**{"type": "boolean", "x-ui:title": 42, "x-ui:order": 20})
        )
        self.assertEqual(None, meta.title)
        self.assertEqual(20, meta.order)

        meta = FieldMeta.from_schema(
            "x",
            Schema(
                **{"type": "boolean", "x-ui:title": "Interpolate", "x-ui:order": [0, 1]}
            ),
        )
        self.assertEqual("Interpolate", meta.title)
        self.assertEqual(None, meta.order)

    def test_to_non_nullable(self):
        meta = FieldMeta.from_schema("x", Schema(**{"type": "boolean"}))
        self.assertIs(False, meta.nullable)
        self.assertIs(meta, meta.to_non_nullable())
        meta = FieldMeta.from_schema(
            "x", Schema(**{"type": "boolean", "nullable": False})
        )
        self.assertIs(False, meta.nullable)
        self.assertIs(meta, meta.to_non_nullable())

        meta = FieldMeta.from_schema(
            "x", Schema(**{"type": "boolean", "nullable": True})
        )
        self.assertIs(True, meta.nullable)
        nn_meta = meta.to_non_nullable()
        self.assertIs(False, nn_meta.nullable)
        self.assertEqual(
            Schema(**{"type": "boolean", "nullable": False}), nn_meta.schema_
        )
        self.assertIs(True, nn_meta.nullable_parent)

    # noinspection PyMethodMayBeStatic
    def test_pydantic_deserialization_with_extra_fields(self):
        """Ensure that pydantic deserializes extra fields as expected."""

        class MyModel(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(
                extra="allow",
            )
            xGui: Annotated[dict[str, Any] | None, pydantic.Field(None, alias="x-gui")]

        model = MyModel(
            **{
                "x-gui": {"widget": "slider"},
                "x-ui": {"widget": "select"},
                "x-ui:widget": "select",
            }
        )

        assert model.xGui == {"widget": "slider"}
        assert model.model_extra["x-ui"] == {"widget": "select"}
        assert model.model_extra["x-ui:widget"] == "select"
        assert model.model_dump() == {
            "x-ui": {"widget": "select"},
            "x-ui:widget": "select",
            "xGui": {"widget": "slider"},
        }
