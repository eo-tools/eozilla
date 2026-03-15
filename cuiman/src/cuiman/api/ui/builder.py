from __future__ import annotations

from typing import Any

from gavicore.models import DataType
from .field import UIFieldInfo
from .nodes import ArrayNode, FieldNode, ObjectNode, PrimitiveNode
from .state import PlainStateFactory, StateFactory


class NodeBuilder:
    def __init__(self, state_factory: StateFactory | None = None):
        self.state_factory = state_factory or PlainStateFactory()

    def build(self, field: UIFieldInfo, parent: FieldNode | None = None) -> FieldNode:
        initial = field.schema_.default
        kind = field.schema_.type

        if kind == DataType.object:
            node = ObjectNode(
                field=field,
                state=self.state_factory.create(initial=initial, field=field),
                parent=parent,
            )
            for child_field in field.children or []:
                node.add_child(self.build(child_field, parent=node))
            return node

        if kind == DataType.array:
            node = ArrayNode(
                field=field,
                state=self.state_factory.create(initial=initial or [], field=field),
                item_state_factory=self.state_factory,
                parent=parent,
            )
            defaults = initial or []
            item_field = (field.children or [None])[0]
            if item_field is not None:
                for item_default in defaults:
                    item_node = self.build(
                        _clone_with_default(item_field, item_default), parent=node
                    )
                    node.add_item(item_node)
            return node

        return PrimitiveNode(
            field=field,
            state=self.state_factory.create(initial=initial, field=field),
            parent=parent,
        )


def _clone_with_default(field: UIFieldInfo, default: Any) -> UIFieldInfo:
    data = field.model_dump(by_alias=True)
    schema = dict(data["schema"])
    schema["default"] = default
    data["schema"] = schema
    return UIFieldInfo.model_validate(data)
