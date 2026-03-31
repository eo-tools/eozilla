#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod

from gavicore.models import DataType

from .base import Field
from .context import FieldContext
from .meta import FieldMeta


class FieldFactory(ABC):
    """
    Field factories are used to create UI fields from
    field metadata and other context data.
    The applicability of a factory for given field
    metadata is determined by an integer score value.
    """

    @abstractmethod
    def get_score(self, meta: FieldMeta) -> int:
        """
        Get the score of this factory for the given field metadata.
        The score is proportional to the factory's ability to create
        a field for the field metadata.
        A negative or zero score indicates the factory's unability.
        """

    @abstractmethod
    def create_field(self, ctx: FieldContext) -> Field:
        """Create the UI field for the given field context."""


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class FieldFactoryBase(FieldFactory, ABC):
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

    def get_score(self, meta: FieldMeta) -> int:
        """Get the score for a field based on its data type."""
        schema = meta.schema_
        if schema.nullable:
            return self.get_nullable_score(meta)
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

    def get_object_score(self, meta: FieldMeta) -> int:
        """Get the score for a field of type "object"."""
        return 0

    def get_array_score(self, meta: FieldMeta) -> int:
        """Get the score for a field of type "array"."""
        return 0

    def get_string_score(self, meta: FieldMeta) -> int:
        """Get the score for a field of type "string"."""
        return 0

    def get_number_score(self, meta: FieldMeta) -> int:
        """Get the score for a field of type "number"."""
        return 0

    def get_integer_score(self, meta: FieldMeta) -> int:
        """Get the score for a field of type "integer"."""
        return 0

    def get_boolean_score(self, meta: FieldMeta) -> int:
        """Get the score for a field of type "boolean"."""
        return 0

    def get_nullable_score(self, meta: FieldMeta) -> int:
        """Get the score for a nullable field."""
        return 0

    def get_untyped_score(self, meta: FieldMeta) -> int:
        """Get the score for a field that has no explicit type."""
        return 0

    def create_field(self, ctx: FieldContext) -> Field:
        """Create a UI field based on its data type."""
        # TODO: we should also respect the case `not ctx.schema.required`,
        #   Check if this could be the treated as `ctx.schema.nullable`.
        if ctx.schema.nullable:
            return self.create_nullable_field(ctx)
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

    def create_object_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value of type "object"."""
        raise NotImplementedError

    def create_array_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value of type "array"."""
        raise NotImplementedError

    def create_string_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value of type "string"."""
        raise NotImplementedError

    def create_number_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value of type "number"."""
        raise NotImplementedError

    def create_integer_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value of type "integer"."""
        raise NotImplementedError

    def create_boolean_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value of type "boolean"."""
        raise NotImplementedError

    def create_nullable_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value that is nullable."""
        raise NotImplementedError

    def create_untyped_field(self, ctx: FieldContext) -> Field:
        """Create a UI field for a value with no explicit type specified."""
        raise NotImplementedError
