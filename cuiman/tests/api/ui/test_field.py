#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from typing import Any
from unittest import TestCase

from cuiman.api.ui import UIBuilderContext
from cuiman.api.ui.field import UIBuilder, UIField, UIFieldBase, UIFieldFactory
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
        views = [uif.get_view() for uif in child_ui_fields]
        view_models = [uif.get_view_model() for uif in child_ui_fields]
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
        self.vm = ArrayViewModel(field_meta)
        self.view = ListEditor()

    def get_view_model(self) -> ArrayViewModel:
        return self.vm

    def get_view(self) -> ListEditor:
        return self.view


class MyTextField(UIFieldBase[PrimitiveViewModel[str], TextField]):
    def __init__(self, field_meta: UIFieldMeta):
        super().__init__(field_meta)
        self.node = PrimitiveViewModel(field_meta)
        self.text_field = TextField()

    def get_view_model(self) -> PrimitiveViewModel[str]:
        return self.node

    def get_view(self) -> TextField:
        return self.text_field


# -----------


class MyObjectFactory(UIFieldFactory):
    def compute_field_score(self, _ctx, field_meta: UIFieldMeta) -> int:
        return 1 if field_meta.schema_.type == DataType.object else 0

    def create_field(self, ctx: UIBuilderContext, field_meta: UIFieldMeta) -> UIField:
        path = [field_meta.name]
        child_ui_fields = [
            ctx.builder.create_ui(fi, path + [fi.name])
            for fi in (field_meta.children or [])
        ]
        return MyObjectField(field_meta, child_ui_fields)


class MyArrayFactory(UIFieldFactory):
    def compute_field_score(self, _ctx, field_meta: UIFieldMeta) -> int:
        return 1 if field_meta.schema_.type == DataType.array else 0

    def create_field(self, _ctx, field_meta: UIFieldMeta) -> UIField:
        return MyArrayField(field_meta)


class MyTextFactory(UIFieldFactory):
    def compute_field_score(self, _ctx, field_meta: UIFieldMeta) -> int:
        return 1 if field_meta.schema_.type == DataType.string else 0

    def create_field(self, _ctx, field_meta: UIFieldMeta) -> UIField:
        return MyTextField(field_meta)


# -----------


class UIBuilderTest(TestCase):
    def test_ui_builder(self):
        b = UIBuilder()
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
        field = b.create_ui(field_meta, [field_meta.name])
        self.assertIsInstance(field, MyObjectField)
