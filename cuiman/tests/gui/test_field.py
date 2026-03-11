from typing import Annotated
from unittest import TestCase

import pydantic
from pydantic import ConfigDict

from cuiman.gui.generator.field import UIFieldInfo
from gavicore.models import InputDescription, OutputDescription


class FromInputDescriptionTest(TestCase):
    def test_empty_input(self):
        field_info = UIFieldInfo.from_input_description(InputDescription(schema={}))
        self.assertEqual(UIFieldInfo(), field_info)


class FromOutputDescriptionTest(TestCase):
    def test_empty_output(self):
        field_info = UIFieldInfo.from_output_description(OutputDescription(schema={}))
        self.assertEqual(UIFieldInfo(), field_info)


def test_deserialization_with_extension_fields():
    class MyModel(pydantic.BaseModel):
        model_config = ConfigDict(
            extra="allow",
        )
        title: Annotated[str | None, pydantic.Field(...)] = None

    model = MyModel(
        **{
            "x-ui": {"widget": "select"},
            "x-ui:widget": "select",
        }
    )

    assert model.title is None
