#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod

from gavicore.models import DataType

from ..vm import ViewModel
from ..vm.object import DynamicObjectViewModel
from .base import UIField
from .context import UIFieldContext
from .meta import UIFieldGroup, UIFieldMeta


class UIFieldFactory(ABC):
    @abstractmethod
    def get_score(self, meta: UIFieldMeta) -> int:
        """Get the score of this factory for the given field metadata."""

    @abstractmethod
    def create_field(self, ctx: UIFieldContext) -> UIField:
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

    TODO: explain special treatment of nullable fields
    """

    def get_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field based on its data type."""
        schema = meta.schema_
        if schema.nullable:
            return self.get_null_score(meta)
        match schema.type:
            case DataType.object:
                return self.get_object_score(meta)
            case DataType.array:
                return self.get_array_score(meta)
            case DataType.string:
                return self.get_string_score(meta)
            case DataType.number:
                return self.get_number_score(meta)
            case DataType.integer:
                return self.get_integer_score(meta)
            case DataType.boolean:
                return self.get_boolean_score(meta)
            case _:
                return self.get_untyped_score(meta)

    def get_object_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field of type "object"."""
        return 0

    def get_array_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field of type "array"."""
        return 0

    def get_string_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field of type "string"."""
        return 0

    def get_number_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field of type "number"."""
        return 0

    def get_integer_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field of type "integer"."""
        return 0

    def get_boolean_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field of type "boolean"."""
        return 0

    def get_null_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a nullable field."""
        return 0

    def get_untyped_score(self, meta: UIFieldMeta) -> int:
        """Get the score for a field that has no explicit type."""
        return 0

    def create_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field based on its data type."""
        if ctx.schema.nullable:
            return self.create_null_field(ctx)
        match ctx.schema.type:
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

    def create_object_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value of type "object"."""
        raise NotImplementedError

    def create_array_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value of type "array"."""
        raise NotImplementedError

    def create_string_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value of type "string"."""
        raise NotImplementedError

    def create_number_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value of type "number"."""
        raise NotImplementedError

    def create_integer_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value of type "integer"."""
        raise NotImplementedError

    def create_boolean_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value of type "boolean"."""
        raise NotImplementedError

    def create_null_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value that is nullable."""
        raise NotImplementedError

    def create_untyped_field(self, ctx: UIFieldContext) -> UIField:
        """Create a UI field for a value with no explicit type given."""
        raise NotImplementedError


class NestedObjectFactory(UIFieldFactory):
    """
    A convenient base class for UI field factories that can create
    container UI fields like panels that align their items
    either in a row or column.
    """

    def get_score(self, meta: UIFieldMeta) -> int:
        """
        Compute the score. Will return 0 for all fields except of type "object".
        Will return 10 if the layout is specified, otherwise 1.
        """
        if meta.schema_.type != DataType.object:
            return 0
        return 10 if meta.layout is not None else 1

    def create_field(self, ctx: UIFieldContext) -> UIField:
        """
        Create a UI field for a value of type "object".
        """
        assert ctx.schema.type == DataType.object
        assert ctx.meta.layout is not None
        group: UIFieldGroup
        if ctx.meta.layout == "row":
            group = UIFieldGroup(type="row")
        elif ctx.meta.layout == "column":
            group = UIFieldGroup(type="column")
        else:
            assert isinstance(ctx.meta.layout, UIFieldGroup)
            group = ctx.meta.layout
        view_model = DynamicObjectViewModel(ctx.meta)
        return self._from_group(ctx, group, view_model, dict(ctx.meta.properties))

    @abstractmethod
    def create_row_field(
        self, ctx: UIFieldContext, view_model: ViewModel, children: list[UIField]
    ) -> UIField:
        """Create a panel field with given children aligned in a row."""

    @abstractmethod
    def create_column_field(
        self, ctx: UIFieldContext, view_model: ViewModel, children: list[UIField]
    ) -> UIField:
        """Create a panel field with given children aligned in a column."""

    def _from_group(
        self,
        ctx: UIFieldContext,
        group: UIFieldGroup,
        view_model: DynamicObjectViewModel,
        properties: dict[str, UIFieldMeta],
    ) -> UIField:
        child_fields: list[UIField]
        if not group.items:
            child_fields = [
                ctx.create_child_field(prop_meta) for prop_meta in properties.values()
            ]
            properties.clear()
        else:
            child_fields = []
            for group_item in group.items:
                if isinstance(group_item, UIFieldGroup):
                    child_field = self._from_group(
                        ctx, group_item, view_model, properties
                    )
                else:
                    assert isinstance(group_item, str)
                    assert isinstance(ctx.meta.properties, dict)
                    prop_name: str = group_item
                    prop_meta = ctx.meta.properties.get(prop_name)
                    if prop_meta is None:
                        raise ValueError(
                            f"property {prop_name!r} not found in object "
                            f"field {ctx.meta.name!r}"
                        )
                    child_field = ctx.create_child_field(prop_meta)
                    properties.pop(prop_name)
                child_fields.append(child_field)

        for child_field in child_fields:
            view_model.define_property(child_field.meta.name, child_field.view_model)

        if group.type == "row":
            return self.create_row_field(ctx, view_model, child_fields)
        else:
            return self.create_column_field(ctx, view_model, child_fields)
