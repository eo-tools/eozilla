#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TYPE_CHECKING, Any

from gavicore.models import DataType, Schema
from gavicore.util.undefined import UNDEFINED, UndefinedType

from ..vm import (
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
    ViewModel,
)
from .base import Field
from .meta import FieldMeta

if TYPE_CHECKING:
    from .builder import FieldBuilder


class FieldContext:
    """The context object passed to the UI field factories."""

    def __init__(
        self,
        *,
        builder: "FieldBuilder",
        meta: FieldMeta,
        initial_value: Any | UndefinedType = UNDEFINED,
        parent_ctx: "FieldContext | None" = None,
    ):
        self._parent_ctx = parent_ctx
        self._builder = builder
        self._meta = meta
        self._vm_builder = UIViewModelBuilder(self)
        self._initial_value = (
            meta.get_initial_value()
            if isinstance(initial_value, UndefinedType)
            else initial_value
        )

    @property
    def meta(self) -> FieldMeta:
        return self._meta

    @property
    def name(self) -> str:
        return self._meta.name

    @property
    def schema(self) -> Schema:
        return self._meta.schema_

    @property
    def vm(self) -> "UIViewModelBuilder":
        return self._vm_builder

    @property
    def initial_value(self) -> Any:
        return self._initial_value

    @property
    def path(self) -> list[str]:
        if self._parent_ctx is not None:
            return self._parent_ctx.path + [self.name]
        return [self.name]

    def create_child_fields(self) -> dict[str, Field]:
        return {
            child_meta.name: self.create_child_field(child_meta)
            for child_meta in (self.meta.children or [])
        }

    def create_property_fields(self) -> dict[str, Field]:
        return {
            prop_name: self.create_child_field(prop_meta)
            for prop_name, prop_meta in (self.meta.properties.items())
        }

    def create_child_field(self, child_meta: FieldMeta) -> Field:
        """Create a new field for the given field metadata."""
        child_ctx = self._create_child_ctx(child_meta)
        # noinspection PyProtectedMember
        return self._builder._create_field(child_ctx)

    def _create_child_ctx(self, child_meta: FieldMeta) -> "FieldContext":
        initial_value = self.initial_value
        child_name = child_meta.name
        if (
            self.schema.type == DataType.object
            and isinstance(initial_value, dict)
            and child_name in initial_value
        ):
            child_value = initial_value[child_name]
        else:
            child_value = child_meta.get_initial_value()
        return FieldContext(
            builder=self._builder,
            meta=child_meta,
            initial_value=child_value,
            parent_ctx=self,
        )


class UIViewModelBuilder:
    """
    A convenient builder for view models available
    from the [UIBuilderContext][UIBuilderContext].
    """

    def __init__(self, ctx: FieldContext):
        self._ctx = ctx

    def primitive(self) -> PrimitiveViewModel:
        return PrimitiveViewModel(self._ctx.meta, value=self._ctx.initial_value)

    def array(self) -> ArrayViewModel:
        return ArrayViewModel(self._ctx.meta, value=self._ctx.initial_value)

    def object(
        self,
        properties: dict[str, ViewModel] | None = None,
    ) -> ObjectViewModel:
        return ObjectViewModel(
            self._ctx.meta,
            value=(self._ctx.initial_value if properties is None else UNDEFINED),
            properties=properties,
        )

    def nullable(
        self,
        inner: ViewModel | None = None,
    ) -> NullableViewModel:
        return NullableViewModel(
            self._ctx.meta,
            value=self._ctx.initial_value,
            inner=inner,
        )
