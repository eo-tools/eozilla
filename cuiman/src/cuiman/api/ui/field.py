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
    @abstractmethod
    def get_meta(self) -> UIFieldMeta:
        """Return the field metadata."""

    @abstractmethod
    def get_view_model(self) -> VMT:
        """Return the node use by this field."""

    @abstractmethod
    def get_view(self) -> VT:
        """Return the node use by this field."""


class UIFieldBase(Generic[VMT, VT], UIField[VMT, VT], ABC):
    def __init__(self, meta: UIFieldMeta):
        self._meta = meta

    def get_meta(self) -> UIFieldMeta:
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
    def get_score(self, ctx: UIBuilderContext) -> int:
        """Get the score of this factory for the given builder context."""

    @abstractmethod
    def create_field(self, ctx: UIBuilderContext) -> UIField:
        """Create the UI field for the given builder context."""


class UIFieldFactoryBase(UIFieldFactory, ABC):
    def get_score(self, ctx: UIBuilderContext) -> int:
        schema_type = ctx.schema.type
        if schema_type == DataType.object:
            return self.get_object_score(ctx)
        elif schema_type == DataType.array:
            return self.get_array_score(ctx)
        elif schema_type is not None:
            return self.get_primitive_score(ctx)
        else:
            return self.get_untyped_score(ctx)

    def get_object_score(self, ctx: UIBuilderContext) -> int:
        return 0

    def get_array_score(self, ctx: UIBuilderContext) -> int:
        return 0

    def get_primitive_score(self, ctx: UIBuilderContext) -> int:
        return 0

    def get_untyped_score(self, ctx: UIBuilderContext) -> int:
        return 0

    def create_field(self, ctx: UIBuilderContext) -> UIField[VMT, VT]:
        schema_type = ctx.schema.type
        if schema_type == DataType.object:
            return self.create_object_field(ctx)
        elif schema_type == DataType.array:
            return self.create_array_field(ctx)
        elif schema_type is not None:
            return self.create_primitive_field(ctx)
        else:
            return self.create_untyped_field(ctx)

    def create_object_field(self, ctx: UIBuilderContext) -> UIField[VMT, VT]:
        raise NotImplementedError

    def create_array_field(self, ctx: UIBuilderContext) -> UIField[VMT, VT]:
        raise NotImplementedError

    def create_primitive_field(self, ctx: UIBuilderContext) -> UIField[VMT, VT]:
        raise NotImplementedError

    def create_untyped_field(self, ctx: UIBuilderContext) -> UIField[VMT, VT]:
        raise NotImplementedError


class UIFieldBuilder:
    def __init__(self):
        self._factories = []

    def register_factory(self, factory: UIFieldFactory):
        self._factories.append(factory)

    def find_factory(self, ctx: UIBuilderContext) -> UIFieldFactory | None:
        max_score = 0
        best_factory: UIFieldFactory | None = None
        for f in self._factories:
            s = f.get_score(ctx)
            if s > max_score:
                max_score = s
                best_factory = f
        return best_factory

    def create_field(self, ctx: UIBuilderContext) -> UIField:
        factory = self.find_factory(ctx)
        if factory is None:
            raise ValueError(
                f"No factory found for creating a UI for field {'.'.join(ctx.path)!r}"
            )
        return factory.create_field(ctx)

    def create_ctx(
        self, field_meta: UIFieldMeta, parent_ctx: UIBuilderContext | None = None
    ) -> UIBuilderContext:
        return UIBuilderContext(self, field_meta, parent_ctx=parent_ctx)
