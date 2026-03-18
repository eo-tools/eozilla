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
from gavicore.models import DataType, Schema

# -----------


class Component:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Panel(Component):
    pass


class ListEditor(Component):
    pass


class TextField(Component):
    pass


# -----------


class MyObjectField(UIFieldBase[ObjectViewModel, Panel]):
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
        self.panel = Panel(views=views)

    def get_view_model(self) -> ObjectViewModel:
        return self.vm

    def get_view(self) -> Panel:
        return self.panel


class MyArrayField(UIFieldBase[ArrayViewModel, ListEditor]):
    def __init__(self, field_meta: UIFieldMeta):
        super().__init__(field_meta)
        self.vm = ArrayViewModel(field_meta, None, None)
        self.view = ListEditor()

    def get_view_model(self) -> ArrayViewModel:
        return self.vm

    def get_view(self) -> ListEditor:
        return self.view


class MyTextField(UIFieldBase[PrimitiveViewModel[str], TextField]):
    def __init__(self, field_meta: UIFieldMeta):
        super().__init__(field_meta)
        self.node = PrimitiveViewModel(field_meta, None, None)
        self.text_field = TextField()

    def get_view_model(self) -> PrimitiveViewModel[str]:
        return self.node

    def get_view(self) -> TextField:
        return self.text_field


# -----------


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
    def get_primitive_score(self, ctx: UIBuilderContext) -> int:
        return 1 if ctx.schema.type == DataType.string else 0

    def create_field(self, ctx: UIBuilderContext) -> UIField:
        return MyTextField(ctx.field_meta)


# -----------


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

        ctx = b.create_ctx(field_meta)
        field = b.create_field(ctx)
        self.assertIsInstance(field, MyObjectField)
