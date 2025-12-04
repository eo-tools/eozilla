from typing import Any, TypeVar, Type
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

T = TypeVar("T", bound=BaseModel)


class ModelEnhancer:
    """
    Utility that allows for dynamically adding custom fields
    to a Pydantic v2 model class.
    A typical use case is adding vendor-specific extension field
    to API model classes.
    """

    def __init__(self, model: Type[T]):
        self.model = model
        self.fields: dict[str, Field] = {}

    def build(self) -> Type[T]:
        self.model.update(self.fields)
        self.model.model_rebuild()
        self.fields = {}
        return self.model

    def add_field(
        self,
        py_name: str,
        alias_or_field: Field | str,
        annotation: Any | None = None,
        default: Any | None = None,
        **kwargs: Any,
    ) -> "ModelEnhancer":
        if isinstance(alias_or_field, FieldInfo):
            field = alias_or_field
        elif isinstance(alias_or_field, str):
            alias = alias_or_field
            field = Field(
                default=default,
                annotation=annotation,
                validation_alias=alias,
                serialization_alias=alias,
                **kwargs,
            )
        else:
            raise TypeError(
                "alias_or_field argument must by a pydantic.Field or a JSON field name"
            )
        self.fields[py_name] = field
        return self
