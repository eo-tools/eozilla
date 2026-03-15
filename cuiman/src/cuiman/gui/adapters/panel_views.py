from __future__ import annotations

import panel as pn

from cuiman.api.ui.nodes import ArrayNode, FieldNode, ObjectNode, PrimitiveNode
from cuiman.api.ui.view import ViewFactory, ViewRegistry


def _field_label(node: FieldNode) -> str:
    return node.field.title or node.field.name


class PanelObjectFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        return 100 if isinstance(node, ObjectNode) else -1

    def create(self, node: FieldNode, registry: ViewRegistry):
        children = [registry.render(child) for child in node.children]
        return pn.Column(*children, name=_field_label(node))


class PanelArrayFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        return 100 if isinstance(node, ArrayNode) else -1

    def create(self, node: FieldNode, registry: ViewRegistry):
        item_views = [registry.render(item) for item in node.items]
        header = pn.pane.Markdown(f"**{_field_label(node)}**")
        return pn.Column(header, *item_views)


class PanelSliderFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        if not isinstance(node, PrimitiveNode):
            return -1
        if node.field.widget == "slider":
            return 300
        return -1

    def create(self, node: FieldNode, registry: ViewRegistry):
        state = getattr(node.state, "owner", None)
        if state is None:
            raise TypeError("PanelSliderFactory requires ParamState")
        start = node.field.minimum if node.field.minimum is not None else 0
        end = node.field.maximum if node.field.maximum is not None else 100
        return pn.widgets.FloatSlider.from_param(
            state.param.value,
            name=_field_label(node),
            start=start,
            end=end,
        )


class PanelCheckboxFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        if not isinstance(node, PrimitiveNode):
            return -1
        if (
            node.field.widget in {"checkbox", "switch"}
            or node.field.schema_.type == "boolean"
        ):
            return 250
        return -1

    def create(self, node: FieldNode, registry: ViewRegistry):
        state = getattr(node.state, "owner", None)
        if state is None:
            raise TypeError("PanelCheckboxFactory requires ParamState")
        return pn.widgets.Checkbox.from_param(
            state.param.value,
            name=_field_label(node),
        )


class PanelSelectFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        if not isinstance(node, PrimitiveNode):
            return -1
        if node.field.widget in {"select", "radiobutton", "radiogroup"}:
            return 260
        if node.field.schema_.enum:
            return 200
        return -1

    def create(self, node: FieldNode, registry: ViewRegistry):
        state = getattr(node.state, "owner", None)
        if state is None:
            raise TypeError("PanelSelectFactory requires ParamState")
        options = node.field.schema_.enum or []
        return pn.widgets.Select.from_param(
            state.param.value,
            name=_field_label(node),
            options=options,
        )


class PanelTextFactory(ViewFactory):
    def score(self, node: FieldNode) -> int:
        if not isinstance(node, PrimitiveNode):
            return -1
        if node.field.widget == "textarea":
            return 280
        if node.field.widget in {"text", "password"}:
            return 270
        if node.field.schema_.type == "string":
            return 150
        if node.field.schema_.type in {"number", "integer"}:
            return 140
        return -1

    def create(self, node: FieldNode, registry: ViewRegistry):
        state = getattr(node.state, "owner", None)
        if state is None:
            raise TypeError("PanelTextFactory requires ParamState")
        if node.field.widget == "textarea":
            return pn.widgets.TextAreaInput.from_param(
                state.param.value,
                name=_field_label(node),
                placeholder=node.field.placeholder or "",
            )
        if node.field.widget == "password" or node.field.password:
            return pn.widgets.PasswordInput.from_param(
                state.param.value,
                name=_field_label(node),
                placeholder=node.field.placeholder or "",
            )
        if node.field.schema_.type in {"number", "integer"}:
            return pn.widgets.FloatInput.from_param(
                state.param.value,
                name=_field_label(node),
                placeholder=node.field.placeholder or "",
            )
        return pn.widgets.TextInput.from_param(
            state.param.value,
            name=_field_label(node),
            placeholder=node.field.placeholder or "",
        )


def register_default_panel_factories(registry: ViewRegistry) -> None:
    registry.register(PanelObjectFactory())
    registry.register(PanelArrayFactory())
    registry.register(PanelSliderFactory())
    registry.register(PanelCheckboxFactory())
    registry.register(PanelSelectFactory())
    registry.register(PanelTextFactory())
