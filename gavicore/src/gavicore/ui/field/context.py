#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TYPE_CHECKING, Any, Generic

from gavicore.models import DataType, Schema
from gavicore.util.undefined import Undefined

from ..vm import (
    AnyViewModel,
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
    ViewModel,
)
from .base import FT, VT
from .meta import FieldMeta

if TYPE_CHECKING:
    from .generator import FieldGenerator
    from .layout import LayoutFunction


class FieldContext(Generic[FT, VT]):
    """The context object passed to a UI field factory."""

    def __init__(
        self,
        *,
        generator: "FieldGenerator[FT, VT]",
        meta: FieldMeta,
        initial_value: Any | Undefined = Undefined.value,
        no_label: bool = False,
        parent_ctx: "FieldContext[FT, VT] | None" = None,
    ):
        self._parent_ctx = parent_ctx
        self._generator = generator
        self._meta = meta
        self._vm_factory = ViewModelFactory(self)
        self._initial_value = (
            meta.get_initial_value()
            if isinstance(initial_value, Undefined)
            else initial_value
        )
        self._no_label = no_label

    @property
    def meta(self) -> FieldMeta:
        """The field metadata."""
        return self._meta

    @property
    def name(self) -> str:
        """The name from field metadata."""
        return self._meta.name

    @property
    def label(self) -> str:
        """The name from field metadata."""
        return self._meta.label if not self._no_label else ""

    @property
    def schema(self) -> Schema:
        """The OpenAPI Schema from field metadata."""
        return self._meta.schema_

    @property
    def vm(self) -> "ViewModelFactory":
        """The view model factory."""
        return self._vm_factory

    @property
    def initial_value(self) -> Any:
        """An initial value."""
        return self._initial_value

    @property
    def path(self) -> list[str]:
        """The path of this field context as list of field names."""
        if self._parent_ctx is not None:
            return self._parent_ctx.path + [self.name]
        return [self.name]

    def layout(self, layout_function: "LayoutFunction", views: dict[str, VT]) -> VT:
        """Layout the given views using the field metadata's `layout` property."""
        from .layout import LayoutManager

        return LayoutManager(layout_function, views).layout(self)

    def create_property_fields(self) -> dict[str, FT]:
        """Create property fields given that this
        context's field is of type "object".
        """
        assert isinstance(self.meta.properties, dict)
        return {
            prop_name: self.create_child_field(prop_meta)
            for prop_name, prop_meta in self.meta.properties.items()
        }

    def create_item_field(self) -> FT:
        """Create a new item field given that this
        context's field is of type "array".
        """
        assert isinstance(self.meta.items, FieldMeta)
        return self.create_child_field(self.meta.items)

    def create_child_field(self, child_meta: FieldMeta, no_label: bool = False) -> FT:
        """Create a new field for the given child field metadata."""
        child_ctx = self._create_child_ctx(child_meta, no_label=no_label)
        # noinspection PyProtectedMember
        return self._generator._generate_field(child_ctx)

    def _create_child_ctx(
        self, child_meta: FieldMeta, no_label: bool = False
    ) -> "FieldContext[FT, VT]":
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
            generator=self._generator,
            meta=child_meta,
            initial_value=child_value,
            parent_ctx=self,
            no_label=no_label,
        )


class ViewModelFactory:
    """
    A convenience factory for view models. Made available
    as [`ctx.vm`][FieldContext.vm].
    """

    def __init__(self, ctx: FieldContext):
        self._ctx = ctx

    def any(self):
        return AnyViewModel(self._ctx.meta, value=self._ctx.initial_value)

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
            value=(self._ctx.initial_value if properties is None else Undefined.value),
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
