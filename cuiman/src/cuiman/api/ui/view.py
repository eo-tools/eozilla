from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .nodes import ArrayNode, FieldNode, ObjectNode


class ViewFactory(ABC):
    @abstractmethod
    def score(self, node: FieldNode) -> int:
        raise NotImplementedError

    @abstractmethod
    def create(self, node: FieldNode, registry: "ViewRegistry") -> Any:
        raise NotImplementedError


class ViewRegistry:
    def __init__(self):
        self.factories: list[ViewFactory] = []

    def register(self, factory: ViewFactory) -> None:
        self.factories.append(factory)

    def resolve(self, node: FieldNode) -> ViewFactory:
        scored = [(factory.score(node), factory) for factory in self.factories]
        scored = [item for item in scored if item[0] >= 0]
        if not scored:
            raise LookupError(f"No view factory for field {node.field.name!r}")
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def render(self, node: FieldNode) -> Any:
        return self.resolve(node).create(node, self)


class CompositeViewFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        if isinstance(node, (ObjectNode, ArrayNode)):
            return 10
        return -1

    @abstractmethod
    def create(self, node: FieldNode, registry: "ViewRegistry") -> Any:
        raise NotImplementedError
