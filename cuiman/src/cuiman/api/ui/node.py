#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from abc import ABC, abstractmethod
from typing import Any, TypeAlias, TypeVar, Callable

from .field import UIFieldInfo
from .state import ValueState


T = TypeVar("T")

FieldNodeObserver: TypeAlias = Callable[["FieldNode.ChangeEvent"], None]


class FieldNode(ABC):
    UNDEFINED = object()

    class ChangeEvent:
        def __init__(self, source: "FieldNode", new_value: Any, old_value: Any):
            self.source = source
            self.new_value = new_value
            self.old_value = old_value

    def __init__(
        self,
        field: UIFieldInfo,
        parent: "FieldNode | None" = None,
    ):
        self.field = field
        self.parent = parent
        self._observers: list[FieldNodeObserver] = []

    @abstractmethod
    def get(self) -> Any:
        """Get the current value."""

    def set(self, new_value: Any) -> None:
        """Set the current value."""
        old_value = self.get()
        if new_value != old_value:
            self._set(new_value)
            for observer in self._observers:
                observer(self.ChangeEvent(self, new_value, old_value))

    @abstractmethod
    def _set(self, value: Any) -> None:
        """Set the current value."""


class PrimitiveNode(FieldNode):
    def __init__(
        self,
        field: UIFieldInfo,
        parent: "FieldNode | None" = None,
        initial_value: Any = None,
    ):
        super().__init__(field, parent)
        self._value = initial_value

    def get(self):
        return self._value

    def _set(self, value: Any) -> None:
        self._value = value


class ObjectNode(FieldNode):
    def __init__(
        self, field: UIFieldInfo, parent: FieldNode | None = None, *children: FieldNode, initial_value: Any = None
    ):
        super().__init__(field=field, parent=parent)
        self._children = children

    def get(self) -> dict[str, Any]:
        return {node.field.name: node.get() for node in self._children}

    def _set(self, value: dict[str, Any]) -> :
        return value


class ArrayNode(FieldNode):
    def __init__(
        self,
        field: UIFieldInfo,
        state: ValueState,
        parent: FieldNode | None = None,
    ):
        super().__init__(field=field, state=state, parent=parent)
        self.items: list[FieldNode] = []

    def add_item(self, item: FieldNode) -> None:
        item.parent = self
        self.items.append(item)

    def _compute_value(self) -> list[Any]:
        return [item._compute_value() for item in self.items]
