#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any
from unittest import TestCase

from cuiman.api.ui import UIBuilderContext
from cuiman.api.ui.field import (
    UIFieldBuilder,
    UIField,
    UIFieldBase,
    UIFieldFactoryBase,
)
from cuiman.api.ui.fieldmeta import UIFieldMeta
from cuiman.api.ui.vm import (
    ArrayViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
)
from gavicore.models import Schema

# --- A component library --------


class Component:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class PanelComponent(Component):
    pass


class ListEditorComponent(Component):
    pass


class TextComponent(Component):
    pass


# --- UI field adapters --------


class MyObjectField(UIFieldBase[ObjectViewModel, PanelComponent]):
    def __init__(
        self,
        field_meta: UIFieldMeta,
        child_ui_fields: list[UIField],
        value: dict[str, Any] | None = None,
    ):
        super().__init__(field_meta)
        views = [f.get_view() for f in child_ui_fields]
        view_models = [f.get_view_model() for f in child_ui_fields]
        # TODO: we should pass the dict of view_models to ObjectViewModel
        self.vm = ObjectViewModel(field_meta, None, value)
        self.panel = PanelComponent(views=views)

    def get_view_model(self) -> ObjectViewModel:
        return self.vm

    def get_view(self) -> PanelComponent:
        return self.panel


class MyArrayField(UIFieldBase[ArrayViewModel, ListEditorComponent]):
    def __init__(self, field_meta: UIFieldMeta):
        super().__init__(field_meta)
        self.vm = ArrayViewModel(field_meta, None, None)
        self.view = ListEditorComponent(field_meta, None, None)

    def get_view_model(self) -> ArrayViewModel:
        return self.vm

    def get_view(self) -> ListEditorComponent:
        return self.view


class MyTextField(UIFieldBase[PrimitiveViewModel[str], TextComponent]):
    def __init__(self, field_meta: UIFieldMeta):
        super().__init__(field_meta)
        self.node = PrimitiveViewModel(field_meta, None, None)
        self.text_field = TextComponent()

    def get_view_model(self) -> PrimitiveViewModel[str]:
        return self.node

    def get_view(self) -> TextComponent:
        return self.text_field


# --- Factories for the field adapters --------


class MyObjectFactory(UIFieldFactoryBase):
    def get_object_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_object_field(self, ctx: UIBuilderContext) -> UIField:
        child_ui_fields = [
            ctx.create_field(item_meta) for item_meta in (ctx.field_meta.children or [])
        ]
        return MyObjectField(ctx.field_meta, child_ui_fields)


class MyArrayFactory(UIFieldFactoryBase):
    def get_array_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_array_field(self, ctx: UIBuilderContext) -> UIField:
        return MyArrayField(ctx.field_meta)


class MyTextFactory(UIFieldFactoryBase):
    def get_string_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: UIBuilderContext) -> UIField:
        return MyTextField(ctx.field_meta)


# --- UI field builder usage --------


class UIFieldBuilderTest(TestCase):
    def test_builder(self):
        b = UIFieldBuilder()
        b.register_factory(MyArrayFactory())
        b.register_factory(MyObjectFactory())
        b.register_factory(MyTextFactory())

        field_meta = UIFieldMeta.from_schema(
            "root",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "datasets": {"type": "array", "items": {"type": "string"}},
                        "config": {"type": "string"},
                    },
                    "x-layout": "column",
                }
            ),
        )

        ctx = b.create_ctx(field_meta, value={"dataset": []})
        field = b.create_field(ctx)
        self.assertIsInstance(field, MyObjectField)
