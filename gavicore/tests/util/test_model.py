#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Optional

import pytest

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo


class MyModel(BaseModel):
    level: Annotated[int, Field(ge=0)] = 0


class MyModelExtension(BaseModel):
    mode: Optional[str] = None


def test_pydantic_allows_for_dyn_fields():
    model = MyModel(level=3)
    assert model.model_dump(mode="json") == {"level": 3}

    # noinspection PyTypeChecker
    old_fields: dict[str, FieldInfo] = MyModel.model_fields
    # noinspection PyTypeChecker
    new_fields: dict[str, FieldInfo] = MyModelExtension.model_fields
    for name,new_field in new_fields.items():
        if name in old_fields:
            old_field = old_fields[name]
            new_fields[name] = new_field.merge_field_infos(old_field)
    if new_fields:
        if hasattr(MyModel, '__pydantic_fields__'):
            MyModel.__pydantic_fields__.update(new_fields)
        else:
            MyModel.__pydantic_fields__ = dict(new_fields)
        MyModel.__pydantic_complete__ = False
        MyModel.model_rebuild()

    model = MyModel(level=5)
    assert model.model_dump(mode="json") == {"level": 5, 'mode': None}

    model = MyModel(level=7, mode="advanced")
    assert model.model_dump(mode="json") == {"level": 7, "mode": "advanced"}

