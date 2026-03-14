#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Any
from unittest import TestCase

import pydantic

from cuiman.api.ui import UIFieldInfo
from gavicore.models import InputDescription, OutputDescription, Schema


class FromInputDescriptionTest(TestCase):
    def test_precedence(self):
        _assert_source_precedence(self, InputDescription)

    def test_min_occurs_0_max_occurs_1(self):
        schema = Schema(type="string", format="uri", title="Input dataset")
        description = InputDescription(schema=schema, minOccurs=0, maxOccurs=1)
        ui_field_info = UIFieldInfo.from_input_description("datasets", description)
        self.assertEqual(
            UIFieldInfo(
                name="datasets", schema=schema, title="Input dataset", required=False
            ),
            ui_field_info,
        )

    def test_min_occurs_1_max_occurs_1(self):
        schema = Schema(type="string", format="uri", title="Input dataset")
        description = InputDescription(schema=schema, minOccurs=1, maxOccurs=1)
        ui_field_info = UIFieldInfo.from_input_description("datasets", description)
        self.assertEqual(
            UIFieldInfo(
                name="datasets", schema=schema, title="Input dataset", required=True
            ),
            ui_field_info,
        )

    def test_min_occurs_1_max_occurs_unbounded(self):
        schema = Schema(type="string", format="uri")
        description = InputDescription(
            schema=schema, minOccurs=1, maxOccurs="unbounded", title="Input datasets"
        )
        ui_field_info = UIFieldInfo.from_input_description("datasets", description)
        self.assertEqual(
            UIFieldInfo(
                name="datasets",
                title="Input datasets",
                schema=Schema(type="array", items=schema, minItems=1),
                required=True,
                children=[
                    UIFieldInfo(
                        name="datasets_item",
                        schema=schema,
                        required=True,
                    )
                ],
            ),
            ui_field_info,
        )

    def test_tuple_schema(self):
        schema_item_1 = Schema(
            **{"type": "number", "title": "Threshold", "x-ui": {"widget": "slider"}}
        )
        schema_item_2 = Schema(
            **{"type": "boolean", "title": "Boost", "x-ui": {"widget": "switch"}}
        )
        schema = Schema(
            type="array",
            items=[
                schema_item_1,
                schema_item_2,
            ],
        )
        description = InputDescription(schema=schema, title="Performance settings")
        ui_field_info = UIFieldInfo.from_input_description("performance", description)
        self.assertEqual(
            UIFieldInfo(
                name="performance",
                title="Performance settings",
                schema=schema,
                required=True,
                children=[
                    UIFieldInfo(
                        name="performance_item_0",
                        title="Threshold",
                        widget="slider",
                        schema=schema_item_1,
                        required=True,
                    ),
                    UIFieldInfo(
                        name="performance_item_1",
                        title="Boost",
                        widget="switch",
                        schema=schema_item_2,
                        required=True,
                    ),
                ],
            ),
            ui_field_info,
        )

    def test_object_schema(self):
        schema_prop_1 = Schema(
            **{"type": "number", "title": "Threshold", "x-ui": {"widget": "slider"}}
        )
        schema_prop_2 = Schema(
            **{"type": "boolean", "title": "Boost", "x-ui": {"widget": "switch"}}
        )
        schema = Schema(
            type="object",
            properties={
                "threshold": schema_prop_1,
                "boost": schema_prop_2,
            },
            required=["threshold"],
        )
        description = InputDescription(schema=schema, title="Performance settings")
        ui_field_info = UIFieldInfo.from_input_description("performance", description)
        self.assertEqual(
            UIFieldInfo(
                name="performance",
                title="Performance settings",
                schema=schema,
                required=True,
                children=[
                    UIFieldInfo(
                        name="threshold",
                        title="Threshold",
                        widget="slider",
                        schema=schema_prop_1,
                        required=True,
                    ),
                    UIFieldInfo(
                        name="boost",
                        title="Boost",
                        widget="switch",
                        schema=schema_prop_2,
                        required=False,
                    ),
                ],
            ),
            ui_field_info,
        )


class FromOutputDescriptionTest(TestCase):
    def test_precedence(self):
        _assert_source_precedence(self, OutputDescription)


def _assert_source_precedence(
    test: TestCase, description_cls: type[InputDescription] | type[OutputDescription]
):
    _assert_description(
        test,
        description_cls,
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

    _assert_description(
        test,
        description_cls,
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
        expected_props={"title": "The threshold D.2"},
    )

    _assert_description(
        test,
        description_cls,
        description_props={
            "title": "The threshold D.1",
            # "x-ui": {"title": "The threshold D.2"},
            # "x-ui:title": "The threshold D.3",
        },
        schema_props={
            "title": "The threshold S.1",
            "x-ui": {"title": "The threshold S.2"},
            "x-ui:title": "The threshold S.3",
        },
        expected_props={"title": "The threshold D.1"},
    )

    _assert_description(
        test,
        description_cls,
        description_props={
            # "title": "The threshold D.1",
            # "x-ui": {"title": "The threshold D.2"},
            # "x-ui:title": "The threshold D.3",
        },
        schema_props={
            "title": "The threshold S.1",
            "x-ui": {"title": "The threshold S.2"},
            "x-ui:title": "The threshold S.3",
        },
        expected_props={"title": "The threshold S.3"},
    )

    _assert_description(
        test,
        description_cls,
        description_props={
            # "title": "The threshold D.1",
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

    _assert_description(
        test,
        description_cls,
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

    _assert_description(
        test,
        description_cls,
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
        expected_props={},
    )


def _assert_description(
    test: TestCase,
    description_cls: type[InputDescription] | type[OutputDescription],
    description_props: dict[str, Any],
    schema_props: dict[str, Any],
    expected_props: dict[str, Any],
):
    schema = Schema(**schema_props)
    kwargs = {**description_props, "schema": schema}
    if issubclass(description_cls, InputDescription):
        field_info = UIFieldInfo.from_input_description(
            "threshold", InputDescription(**kwargs)
        )
        required = True
    else:
        field_info = UIFieldInfo.from_output_description(
            "threshold",
            OutputDescription(**kwargs),
        )
        required = None

    test.assertEqual(
        UIFieldInfo(
            name="threshold", schema=schema, required=required, **expected_props
        ),
        field_info,
    )


def test_pydantic_deserialization_with_extra_fields():
    """Ensure, pydantic deserializes extra fields as expected."""

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
