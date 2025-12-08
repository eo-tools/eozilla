#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Optional

from pydantic import BaseModel, Field

from gavicore.util.model import extend_model


def test_extend_model_add_fields():
    class MyModel(BaseModel):
        level: Annotated[int, Field(ge=0)] = 0

    class MyExtension(BaseModel):
        mode: Optional[str] = None

    model = MyModel(level=3)
    assert model.model_dump(mode="json") == {"level": 3}

    model_cls = extend_model(MyModel, MyExtension)
    assert model_cls is MyModel

    model = MyModel(level=5)
    assert model.model_dump(mode="json") == {"level": 5, "mode": None}

    # noinspection PyArgumentList
    model = MyModel(level=7, mode="advanced")
    assert model.model_dump(mode="json") == {"level": 7, "mode": "advanced"}


def test_extend_model_merge_fields():
    class MyModel(BaseModel):
        level: Annotated[int, Field(ge=0)] = 0

    class MyExtension(BaseModel):
        level: Annotated[int, Field(title="The level")] = 2

    model = MyModel(level=3)
    assert model.model_dump(mode="json") == {"level": 3}

    model_cls = extend_model(MyModel, MyExtension)
    assert model_cls is MyModel

    model = MyModel(level=5)
    assert model.model_dump(mode="json") == {"level": 5}

    level_field = MyModel.model_fields.get("level")
    assert repr(level_field) == (
        "FieldInfo(annotation=int, required=False, default=2, title='The level', "
        "metadata=[Ge(ge=0)])"
    )


def test_extend_model_empty():
    class MyModel(BaseModel):
        level: Annotated[int, Field(ge=0)] = 0

    class MyEmptyExtension(BaseModel):
        pass

    model = MyModel(level=3)
    assert model.model_dump(mode="json") == {"level": 3}

    model_cls = extend_model(MyModel, MyEmptyExtension)
    assert model_cls is MyModel

    model = MyModel(level=5)
    assert model.model_dump(mode="json") == {"level": 5}
