#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Any
from unittest import TestCase

import pydantic

from cuiman.api.ui import UIFieldInfo
from gavicore.models import InputDescription, OutputDescription


class FromInputDescriptionTest(TestCase):
    def test_empty_input(self):
        field_info = UIFieldInfo.from_input_description(InputDescription(schema={}))
        self.assertEqual(UIFieldInfo(), field_info)


class FromOutputDescriptionTest(TestCase):
    def test_empty_output(self):
        field_info = UIFieldInfo.from_output_description(OutputDescription(schema={}))
        self.assertEqual(UIFieldInfo(), field_info)


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
