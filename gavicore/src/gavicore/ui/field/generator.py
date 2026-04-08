#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any, Callable

from gavicore.util.undefined import Undefined

from .base import Field
from .context import FieldContext
from .factory import FieldFactory
from .meta import FieldMeta
from .registry import FieldFactoryRegistry


class FieldGenerator:
    """
    Entry point for generating fields and field
    forms from field metadata.
    """

    def __init__(self, field_factory_registry: FieldFactoryRegistry | None = None):
        self._field_factory_registry = (
            field_factory_registry
            if field_factory_registry is not None
            else FieldFactoryRegistry()
        )

    def register_field_factory(self, field_factory: FieldFactory) -> Callable[[], None]:
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
    ) -> Field:
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

    def _generate_field(self, ctx: FieldContext) -> Field:
        factory = self._field_factory_registry.lookup(ctx.meta)
        if factory is None:
            # TODO: if a factory cannot be found, the default behaviour
            #  should be to emit a warning and ignore the field, as this will
            #  be a quite common situation.
            raise ValueError(
                f"no factory found for creating a UI for field {'.'.join(ctx.path)!r}"
            )
        return factory.create_field(ctx)
