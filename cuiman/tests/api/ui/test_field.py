#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
from unittest import TestCase

from cuiman.api.ui import (
    UIBuilderContext,
    UIField,
    UIFieldBase,
    UIFieldBuilder,
    UIFieldFactoryBase,
    UIFieldMeta,
)
from cuiman.api.ui.vm import ObjectViewModel, ViewModel
from gavicore.models import Schema

from .libui import (
    Checkbox,
    ListEditor,
    NullableView,
    NumberField,
    Panel,
    TextField,
    View,
    Widget,
)

# --- A component library --------


# --- UI field adapter --------


class LibuiAdapter(UIFieldBase):
    def __init__(self, field_meta: UIFieldMeta, view_model: ViewModel, view: View):
        super().__init__(field_meta)
        self._view_model = view_model
        self._view = view
        self._bind_bidi()

    def get_view_model(self) -> ViewModel:
        return self._view_model

    def get_view(self) -> View:
        return self._view

    def _bind_bidi(self):
        vm = self._view_model
        if isinstance(self._view, Widget):
            widget: Widget = self._view

            def observe_vm(_e):
                widget.value = vm.get()

            def observe_view():
                vm.set(widget.value)

            vm.watch(observe_vm)
            widget.watch(observe_view)


# --- Factories for field adapters --------


class PanelFactory(UIFieldFactoryBase):
    def get_object_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_object_field(self, ctx: UIBuilderContext) -> UIField:
        child_fields = ctx.create_child_fields()
        view_models = {k: f.get_view_model() for k, f in child_fields.items()}
        views = {k: f.get_view() for k, f in child_fields.items()}
        view_model = ctx.vm.object(
            property_view_models=view_models,
        )
        panel = Panel(children=views)
        return LibuiAdapter(ctx.field_meta, view_model, view=panel)


class ListEditorFactory(UIFieldFactoryBase):
    def get_array_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_array_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.array()
        list_editor = ListEditor(value=view_model.get())
        return LibuiAdapter(ctx.field_meta, view_model, view=list_editor)


class TextFieldFactory(UIFieldFactoryBase):
    def get_string_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.primitive()
        text_field = TextField(value=view_model.get())
        return LibuiAdapter(ctx.field_meta, view_model, view=text_field)


class NumberFieldFactory(UIFieldFactoryBase):
    def get_number_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_number_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.primitive()
        number_field = NumberField(value=view_model.get())
        return LibuiAdapter(ctx.field_meta, view_model, view=number_field)


class NullableWidgetFactory(UIFieldFactoryBase):
    def get_null_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_null_field(self, ctx: UIBuilderContext) -> UIField:
        non_nullable_meta = ctx.field_meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        non_nullable_view_model = non_nullable_field.get_view_model()
        non_nullable_view = non_nullable_field.get_view()
        view_model = ctx.vm.nullable(non_nullable_view_model=non_nullable_view_model)
        nullable_widget = NullableView(value=ctx.initial_value, view=non_nullable_view)
        return LibuiAdapter(ctx.field_meta, view_model, view=nullable_widget)


# --- UI field builder usage --------


class UIFieldBuilderTest(TestCase):
    def test_builder(self):
        b = UIFieldBuilder()
        b.register_factory(ListEditorFactory())
        b.register_factory(NullableWidgetFactory())
        b.register_factory(NumberFieldFactory())
        b.register_factory(PanelFactory())
        b.register_factory(TextFieldFactory())

        field_meta = UIFieldMeta.from_schema(
            "root",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "datasets_paths": {
                            "type": "array",
                            "items": {"type": "string", "format": "uri"},
                        },
                        "config_path": {
                            "type": "string",
                            "format": "uri",
                        },
                        "threshold": {
                            "type": "number",
                            "nullable": True,
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "x-layout": "column",
                }
            ),
        )

        field = b.create_field(
            field_meta,
            initial_value={
                "dataset_paths": [],
                "config_path": "my-config.yaml",
                "threshold": None,
            },
        )
        self.assertIsInstance(field, LibuiAdapter)
        view_model = field.get_view_model()
        view = field.get_view()
        self.assertIsInstance(view_model, ObjectViewModel)
        self.assertIsInstance(view, Panel)
        self.assertIsNotNone(view.children)
        self.assertEqual(3, len(view.children))
        self.assertEqual(
            ["datasets_paths", "config_path", "threshold"], list(view.children.keys())
        )
        children = list(view.children.values())
        child_1 = children[0]
        child_2 = children[1]
        child_3 = children[2]
        self.assertIsInstance(child_1, ListEditor)
        self.assertIsInstance(child_2, TextField)
        self.assertIsInstance(child_3, NullableView)
        self.assertIsInstance(child_3.checkbox, Checkbox)
        self.assertIsInstance(child_3.child_view, NumberField)
