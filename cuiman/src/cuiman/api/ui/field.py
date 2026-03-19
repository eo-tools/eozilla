#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from gavicore.models import DataType, Schema
from .fieldmeta import UIFieldMeta
from .vm import ViewModel

VMT = TypeVar("VMT", bound=ViewModel)
VT = TypeVar("VT")


class UIField(Generic[VMT, VT], ABC):
    """
    Adapter that allows using a view `V` from some UI component library
    together with a view model `VMT` of type `ViewModel`.
    """

    @abstractmethod
    def get_view_model(self) -> VMT:
        """Return the node use by this field."""

    @abstractmethod
    def get_view(self) -> VT:
        """Return the node use by this field."""


class UIFieldBase(Generic[VMT, VT], UIField[VMT, VT], ABC):
    """Abstract base class for UI fields."""

    def __init__(self, field_meta: UIFieldMeta):
        self._meta = field_meta

    @property
    def meta(self) -> UIFieldMeta:
        return self._meta


class UIBuilderContext:
    def __init__(
        self,
        builder: "UIFieldBuilder",
        field_meta: UIFieldMeta,
        parent_ctx: "UIBuilderContext | None" = None,
    ):
        self._parent_ctx = parent_ctx
        self._builder = builder
        self._field_meta = field_meta

    @property
    def builder(self) -> "UIFieldBuilder":
        return self._builder

    @property
    def field_meta(self) -> UIFieldMeta:
        return self._field_meta

    @property
    def name(self) -> str:
        return self._field_meta.name

    @property
    def schema(self) -> Schema:
        return self._field_meta.schema_

    @property
    def path(self) -> list[str]:
        if self._parent_ctx is not None:
            return self._parent_ctx.path + [self.name]
        return [self.name]

    def create_field(self, field_meta: UIFieldMeta):
        """Create a new field for the given field metadata."""
        ctx = UIBuilderContext(self._builder, field_meta, parent_ctx=self)
        return self._builder.create_field(ctx)


class UIFieldFactory(ABC):
    @abstractmethod
    def get_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score of this factory for the given field metadata."""

    @abstractmethod
    def create_field(self, ctx: UIBuilderContext) -> UIField:
        """Create the UI field for the given builder context."""


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class UIFieldFactoryBase(UIFieldFactory, ABC):
    """
    A convenient base class for UI field factories that create
    UI fields based on the schema data type.

    You need to override one or more of the `get_{type}_score()`
    methods and return a value greater zero.
    By default, all `get_{type}_score()` return zero.

    Make sure to also implement any `create_{type}_field()` method
    for which `get_{type}_score()` returns a value greater zero.
    By default, all `create_{type}_field()` raise a `NotImplementedError`.
    """

    def get_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field based on its data type."""
        match field_meta.schema_.type:
            case DataType.object:
                return self.get_object_score(field_meta)
            case DataType.array:
                return self.get_array_score(field_meta)
            case DataType.string:
                return self.get_string_score(field_meta)
            case DataType.number:
                return self.get_number_score(field_meta)
            case DataType.integer:
                return self.get_integer_score(field_meta)
            case DataType.boolean:
                return self.get_boolean_score(field_meta)
            case _:
                return self.get_untyped_score(field_meta)

    def get_object_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field of type "object"."""
        return 0

    def get_array_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field of type "array"."""
        return 0

    def get_string_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field of type "string"."""
        return 0

    def get_number_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field of type "number"."""
        return 0

    def get_integer_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field of type "integer"."""
        return 0

    def get_boolean_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field of type "boolean"."""
        return 0

    def get_untyped_score(self, field_meta: UIFieldMeta) -> int:
        """Get the score for a field that has no explicit type."""
        return 0

    def create_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field based on its data type."""
        schema_type = ctx.schema.type
        match schema_type:
            case DataType.object:
                return self.create_object_field(ctx)
            case DataType.array:
                return self.create_array_field(ctx)
            case DataType.string:
                return self.create_string_field(ctx)
            case DataType.number:
                return self.create_number_field(ctx)
            case DataType.integer:
                return self.create_integer_field(ctx)
            case DataType.boolean:
                return self.create_boolean_field(ctx)
            case _:
                return self.create_untyped_field(ctx)

    def create_object_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value of type "object"."""
        raise NotImplementedError

    def create_array_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value of type "array"."""
        raise NotImplementedError

    def create_string_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value of type "string"."""
        raise NotImplementedError

    def create_number_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value of type "number"."""
        raise NotImplementedError

    def create_integer_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value of type "integer"."""
        raise NotImplementedError

    def create_boolean_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value of type "boolean"."""
        raise NotImplementedError

    def create_untyped_field(self, ctx: UIBuilderContext) -> UIField:
        """Create a UI field for a value with no explicit type given."""
        raise NotImplementedError


class UIFieldBuilder:
    def __init__(self):
        self._factories = []

    def register_factory(self, factory: UIFieldFactory):
        self._factories.append(factory)

    def find_factory(self, field_meta: UIFieldMeta) -> UIFieldFactory | None:
        max_score = 0
        best_factory: UIFieldFactory | None = None
        for f in self._factories:
            s = f.get_score(field_meta)
            if s > max_score:
                max_score = s
                best_factory = f
        return best_factory

    def create_ctx(
        self, field_meta: UIFieldMeta, parent_ctx: UIBuilderContext | None = None
    ) -> UIBuilderContext:
        return UIBuilderContext(self, field_meta, parent_ctx=parent_ctx)

    def create_field(self, ctx: UIBuilderContext) -> UIField:
        factory = self.find_factory(ctx.field_meta)
        if factory is None:
            raise ValueError(
                f"No factory found for creating a UI for field {'.'.join(ctx.path)!r}"
            )
        return factory.create_field(ctx)
