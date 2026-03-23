#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import TYPE_CHECKING, Any

from gavicore.util.undefined import UNDEFINED, UndefinedType

from .base import UIField
from .meta import UIFieldMeta

if TYPE_CHECKING:
    from .context import UIFieldContext
    from .factory import UIFieldFactory


class UIFieldBuilder:
    def __init__(self):
        self._factories = []

    def register_factory(self, factory: "UIFieldFactory"):
        self._factories.append(factory)

    def find_factory(self, meta: UIFieldMeta) -> "UIFieldFactory | None":
        max_score = 0
        best_factory: UIFieldFactory | None = None
        for f in self._factories:
            s = f.get_score(meta)
            if s > max_score:
                max_score = s
                best_factory = f
        return best_factory

    def create_field(
        self,
        meta: UIFieldMeta,
        initial_value: Any | UndefinedType = UNDEFINED,
    ) -> UIField:
        from .context import UIFieldContext

        ctx = UIFieldContext(
            builder=self,
            meta=meta,
            initial_value=initial_value,
            parent_ctx=None,
        )
        return self.create_field_for_ctx(ctx)

    def create_field_for_ctx(self, ctx: "UIFieldContext") -> UIField:
        factory = self.find_factory(ctx.meta)
        if factory is None:
            raise ValueError(
                f"no factory found for creating a UI for field {'.'.join(ctx.path)!r}"
            )
        return factory.create_field(ctx)
