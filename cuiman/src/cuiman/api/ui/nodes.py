#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from .field import UIFieldInfo
from .state import ValueState


class FieldNode:
    def __init__(
        self,
        field: UIFieldInfo,
        state: ValueState,
        parent: "FieldNode | None" = None,
    ):
        self.field = field
        self.state = state
        self.parent = parent

    def get(self) -> Any:
        return self.state.get()

    def set(self, value: Any) -> None:
        self.state.set(value)

    def to_python(self) -> Any:
        return self.get()


class PrimitiveNode(FieldNode):
    pass


class ObjectNode(FieldNode):
    def __init__(
        self,
        field: UIFieldInfo,
        state: ValueState,
        parent: FieldNode | None = None,
    ):
        super().__init__(field=field, state=state, parent=parent)
        self.children: list[FieldNode] = []

    def add_child(self, child: FieldNode) -> None:
        child.parent = self
        self.children.append(child)

    def to_python(self) -> dict[str, Any]:
        return {child.field.name: child.to_python() for child in self.children}


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

    def to_python(self) -> list[Any]:
        return [item.to_python() for item in self.items]
