#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TypeVar

from pydantic import BaseModel
from pydantic.fields import FieldInfo

T1 = TypeVar("T1", bound=BaseModel)
T2 = TypeVar("T2", bound=BaseModel)


def extend_model(model_cls: T1, extension_cls: T2) -> T1:
    """
    A utility function that allows for dynamically adding custom fields
    to a Pydantic v2 model class.
    A typical use case is adding vendor-specific extension field
    to API model classes.

    If a field from `extension_cls` exists in `model_cls`,
    their field properties are merged.

    If `extension_cls` has no fields, the function is a no-op.

    Args:
        model_cls: The model class to be enhanced.
        extension_cls: The model class to that provides additional fields.

    Returns:
        The `model_cls` instance.
    """
    # noinspection PyTypeChecker
    old_fields: dict[str, FieldInfo] = model_cls.model_fields
    # noinspection PyTypeChecker
    new_fields: dict[str, FieldInfo] = dict(extension_cls.model_fields)
    if not new_fields:
        return model_cls
    for name, new_field in new_fields.items():
        if name in old_fields:
            old_field = old_fields[name]
            new_fields[name] = FieldInfo.merge_field_infos(old_field, new_field)
    assert hasattr(model_cls, "__pydantic_fields__")
    assert isinstance(model_cls.__pydantic_fields__, dict)
    model_cls.__pydantic_fields__.update(new_fields)
    model_cls.__pydantic_complete__ = False  # type: ignore[misc]
    model_cls.model_rebuild()
    return model_cls
