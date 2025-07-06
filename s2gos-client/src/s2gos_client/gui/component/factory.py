#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

from .component import Component
from .json import JsonSchemaDict, JsonType, JsonValue

if TYPE_CHECKING:
    from .registry import ComponentFactoryRegistry


class ComponentFactory(ABC):
    """
    Factory for components.
    Instances of this class are registered in a `ComponentFactoryRegistry`
    using the combination of a JSON schema type and format
    as registration key.
    """

    @abstractmethod
    def create_component(
        self, value: JsonValue, title: str, schema: JsonSchemaDict
    ) -> Component:
        """
        Create a new component from given JSON schema.

        Args:
            value: the initial JSON input value, may be `None`
            title: a component title
            schema: the schema

        Returns: a component
        """

    @abstractmethod
    def accept(self, schema: JsonSchemaDict) -> bool:
        """
        Check, whether the components produced by this factory
        can use the given schema.
        """


class ComponentFactoryBase(ComponentFactory, ABC):
    """
    Base class for component factories that dedicated to JSON type and/or format.
    """

    type: JsonType | Literal["*"] | None = None
    """
    Specifies the JSON type to use as a registry key.
    The key `"*"` can be used for arbitrary types and requires
    overriding the `accept` method by a suitable implementation
    that recognizes the actual type in the schema.
    The key `None` expects that a type must not be specified
    in a given schema.
    """

    format: str | Literal["*"] | None = None
    """
    Specifies the JSON type to use as a registry key.
    The key `"*"` can be used for arbitrary types and requires
    overriding the `accept` method by a suitable implementation
    that recognizes the actual format in the schema.
    The key `None` expects that a type must not be specified
    in a given schema.
    """

    # noinspection PyShadowingBuiltins
    def accept(self, schema: JsonSchemaDict) -> bool:
        other_type = schema.get("type")
        other_format = schema.get("format")
        type_matches = self.type == other_type or self.type == "*"
        format_matches = self.format == other_format or self.format == "*"
        return type_matches and format_matches

    @classmethod
    def register_in(cls, registry: "ComponentFactoryRegistry"):
        """Register this factory in the given registry."""
        registry.register_factory(cls(), type=cls.type, format=cls.format)
