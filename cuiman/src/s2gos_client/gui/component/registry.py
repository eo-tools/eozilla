#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from collections import defaultdict

from .factory import ComponentFactory
from .json import JsonSchemaDict

KeyType = tuple[str | None, str | None]


class ComponentFactoryRegistry:
    """A registry for component factories."""

    def __init__(self):
        self._factories: dict[KeyType, list[ComponentFactory]] = defaultdict(list)

    # noinspection PyShadowingBuiltins
    def register_factory(
        self,
        factory: ComponentFactory,
        type: str | None,
        format: str | None,
    ):
        """
        Register a component factory using optional
        `type` and `format` as keys.
        """
        self._factories[(type, format)].append(factory)

    def find_factory(self, schema: JsonSchemaDict) -> ComponentFactory | None:
        schema_type: str | None = schema.get("type")  # type: ignore[assignment]
        schema_format: str | None = schema.get("format")  # type: ignore[assignment]
        for t, f in (
            (schema_type, schema_format),
            (schema_type, "*"),
            ("*", schema_format),
            ("*", "*"),
        ):
            candidate_factories = self._factories.get((t, f))
            if candidate_factories:
                # we reverse to have LI-FO behaviour
                for factory in reversed(candidate_factories):
                    if factory.accept(schema):
                        return factory
        return None
