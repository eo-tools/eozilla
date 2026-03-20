#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

from cuiman.api.ui import UIBuilderContext
from cuiman.api.ui.field import (
    UIField,
    UIFieldBase,
    UIFieldBuilder,
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
        ctx: UIBuilderContext,
    ):
        super().__init__(ctx.field_meta)
        child_fields = [
            ctx.create_child_field(item_meta)
            for item_meta in (ctx.field_meta.children or [])
        ]
        views = [f.get_view() for f in child_fields]
        view_models = {f.get_meta().name: f.get_view_model() for f in child_fields}
        self._vm = ObjectViewModel(
            ctx.field_meta,
            initial_value=ctx.initial_value,
            item_view_models=view_models,
        )
        self._panel = PanelComponent(views=views)

    def get_view_model(self) -> ObjectViewModel:
        return self._vm

    def get_view(self) -> PanelComponent:
        return self._panel


class MyArrayField(UIFieldBase[ArrayViewModel, ListEditorComponent]):
    def __init__(self, ctx: UIBuilderContext):
        super().__init__(ctx.field_meta)
        self._vm = ArrayViewModel(ctx.field_meta, ctx.initial_value)
        self._list_editor = ListEditorComponent()

    def get_view_model(self) -> ArrayViewModel:
        return self._vm

    def get_view(self) -> ListEditorComponent:
        return self._list_editor


class MyTextField(UIFieldBase[PrimitiveViewModel[str], TextComponent]):
    def __init__(self, ctx: UIBuilderContext):
        super().__init__(ctx.field_meta)
        self._vm = PrimitiveViewModel(ctx.field_meta, ctx.initial_value)
        self._text_field = TextComponent()

    def get_view_model(self) -> PrimitiveViewModel[str]:
        return self._vm

    def get_view(self) -> TextComponent:
        return self._text_field


# --- Factories for the field adapters --------


class MyObjectFactory(UIFieldFactoryBase):
    def get_object_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_object_field(self, ctx: UIBuilderContext) -> UIField:
        return MyObjectField(ctx)


class MyArrayFactory(UIFieldFactoryBase):
    def get_array_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_array_field(self, ctx: UIBuilderContext) -> UIField:
        return MyArrayField(ctx)


class MyTextFactory(UIFieldFactoryBase):
    def get_string_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: UIBuilderContext) -> UIField:
        return MyTextField(ctx)


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

        field = b.create_field(
            field_meta, initial_value={"dataset": [], "config": "my-config.yaml"}
        )
        self.assertIsInstance(field, MyObjectField)
        view_model = field.get_view_model()
        view = field.get_view()
        self.assertIsInstance(view_model, ObjectViewModel)
        self.assertIsInstance(view, PanelComponent)
