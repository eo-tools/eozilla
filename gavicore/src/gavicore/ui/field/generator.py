#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable, Generic

from gavicore.util.undefined import Undefined

from .base import FT, VT
from .context import FieldContext
from .factory import FieldFactory
from .meta import FieldMeta
from .registry import FieldFactoryRegistry


class FieldGenerator(Generic[FT, VT]):
    """
    Entry point for generating fields and field
    forms from field metadata.
    """

    def __init__(self, field_factory_registry: FieldFactoryRegistry[FT] | None = None):
        self._field_factory_registry = (
            field_factory_registry
            if field_factory_registry is not None
            else FieldFactoryRegistry()
        )

    def register_field_factory(
        self, field_factory: FieldFactory[FT]
    ) -> Callable[[], None]:
        """
        Register a new field factory.

        Args:
            field_factory: A field factory.
        Returns:
            A callable that can be used to register the added field factory.
        """
        return self._field_factory_registry.register(field_factory)

    def generate_field(
        self,
        meta: FieldMeta,
        initial_value: Any | Undefined = Undefined.value,
    ) -> FT:
        """
        Generate a field or form from the given field metadata.

        Args:
            meta: The field metadata.
            initial_value: The optional, initial value for the field.
        Returns:
            The generated field or form.
        """
        ctx = FieldContext(
            generator=self,
            meta=meta,
            initial_value=initial_value,
            parent_ctx=None,
        )
        return self._generate_field(ctx)

    def _generate_field(self, ctx: FieldContext[FT, VT]) -> FT:
        factory = self._field_factory_registry.lookup(ctx.meta)
        if factory is None:
            raise ValueError(
                f"no factory found for creating a UI for field {'.'.join(ctx.path)!r}"
            )
        return factory.create_field(ctx)
