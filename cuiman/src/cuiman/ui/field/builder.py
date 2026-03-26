#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.util.undefined import UNDEFINED, UndefinedType

from .base import Field
from .context import FieldContext
from .meta import FieldMeta
from .registry import FieldFactoryRegistry


class FieldBuilder:
    """A builder for UI fields."""

    def __init__(self, registry: "FieldFactoryRegistry | None" = None):
        self._registry = registry if registry is not None else FieldFactoryRegistry()

    @property
    def registry(self) -> "FieldFactoryRegistry":
        return self._registry

    def create_field(
        self,
        meta: FieldMeta,
        initial_value: Any | UndefinedType = UNDEFINED,
    ) -> Field:
        from .context import FieldContext

        ctx = FieldContext(
            builder=self,
            meta=meta,
            initial_value=initial_value,
            parent_ctx=None,
        )
        return self.create_field_for_ctx(ctx)

    def create_field_for_ctx(self, ctx: "FieldContext") -> Field:
        factory = self._registry.find(ctx.meta)
        if factory is None:
            raise ValueError(
                f"no factory found for creating a UI for field {'.'.join(ctx.path)!r}"
            )
        return factory.create_field(ctx)
