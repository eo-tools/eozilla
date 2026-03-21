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
from cuiman.api.ui.vm import (
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
    ViewModel,
)
from gavicore.models import Schema

from .libui import (
    Checkbox,
    ListEditor,
    NullableView,
    NumberInput,
    Panel,
    Switch,
    TextInput,
    View,
)

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
        def observe_vm(_e):
            self._view.value = self._view_model.value

        def observe_view():
            self._view_model.value = self._view.value

        self._view_model.watch(observe_vm)
        self._view.watch(observe_view)


# --- Factories for field adapters --------


class ObjectFieldFactory(UIFieldFactoryBase):
    def get_object_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_object_field(self, ctx: UIBuilderContext) -> UIField:
        child_fields = ctx.create_child_fields()
        view_models = {k: f.get_view_model() for k, f in child_fields.items()}
        views = {k: f.get_view() for k, f in child_fields.items()}
        view_model = ctx.vm.object(
            property_view_models=view_models,
        )
        view = Panel(children=views)
        return LibuiAdapter(ctx.field_meta, view_model, view=view)


class ArrayFieldFactory(UIFieldFactoryBase):
    def get_array_score(self, ctx: UIBuilderContext) -> int:
        return 1

    def create_array_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.array()
        view = ListEditor(value=view_model._get_value())
        return LibuiAdapter(ctx.field_meta, view_model, view=view)


class StringFieldFactory(UIFieldFactoryBase):
    def get_string_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.primitive()
        view = TextInput(value=view_model._get_value())
        return LibuiAdapter(ctx.field_meta, view_model, view=view)


class NumberFieldFactory(UIFieldFactoryBase):
    def get_number_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_number_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.primitive()
        view = NumberInput(value=view_model._get_value())
        return LibuiAdapter(ctx.field_meta, view_model, view=view)


class BooleanFieldFactory(UIFieldFactoryBase):
    def get_boolean_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_boolean_field(self, ctx: UIBuilderContext) -> UIField:
        view_model = ctx.vm.primitive()
        view = Checkbox(value=view_model._get_value())
        return LibuiAdapter(ctx.field_meta, view_model, view=view)


class NullFieldFactory(UIFieldFactoryBase):
    def get_null_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_null_field(self, ctx: UIBuilderContext) -> UIField:
        non_nullable_meta = ctx.field_meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        non_nullable_view_model = non_nullable_field.get_view_model()
        non_nullable_view = non_nullable_field.get_view()
        view_model = ctx.vm.nullable(non_nullable_view_model=non_nullable_view_model)
        view = NullableView(value=ctx.initial_value, child=non_nullable_view)
        return LibuiAdapter(ctx.field_meta, view_model, view=view)


# --- UI field builder usage --------


class UIFieldBuilderTest(TestCase):
    def test_builder(self):
        b = UIFieldBuilder()
        b.register_factory(ArrayFieldFactory())
        b.register_factory(NullFieldFactory())
        b.register_factory(NumberFieldFactory())
        b.register_factory(BooleanFieldFactory())
        b.register_factory(ObjectFieldFactory())
        b.register_factory(StringFieldFactory())

        field_meta = UIFieldMeta.from_schema(
            "root",
            Schema(
                **{
                    "type": "object",
                    "properties": {
                        "ds_paths": {
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
                        "verbose": {"type": "boolean"},
                    },
                    "x-layout": "column",
                }
            ),
        )

        field = b.create_field(
            field_meta,
            initial_value={
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.75,
                "verbose": False,
            },
        )
        self.assertIsInstance(field, LibuiAdapter)
        view_model = field.get_view_model()
        view = field.get_view()

        #
        # assert that UI composition is as expected
        #

        self.assertIsInstance(view_model, ObjectViewModel)
        self.assertEqual(4, len(view_model))
        self.assertEqual(
            ["ds_paths", "config_path", "threshold", "verbose"],
            list(view_model.property_view_models),
        )
        vm_1 = view_model.property_view_models["ds_paths"]
        vm_2 = view_model.property_view_models["config_path"]
        vm_3 = view_model.property_view_models["threshold"]
        vm_4 = view_model.property_view_models["verbose"]
        self.assertIsInstance(vm_1, ArrayViewModel)
        self.assertIsInstance(vm_2, PrimitiveViewModel)
        self.assertIsInstance(vm_3, NullableViewModel)
        self.assertIsInstance(vm_4, PrimitiveViewModel)
        self.assertIsInstance(view, Panel)
        self.assertIsNotNone(view.children)
        self.assertEqual(4, len(view.children))
        self.assertEqual(
            ["ds_paths", "config_path", "threshold", "verbose"],
            list(view.children.keys()),
        )
        children = list(view.children.values())
        child_1 = children[0]
        child_2 = children[1]
        child_3 = children[2]
        child_4 = children[3]
        self.assertIsInstance(child_1, ListEditor)
        self.assertIsInstance(child_2, TextInput)
        self.assertIsInstance(child_3, NullableView)
        self.assertIsInstance(child_3.child_enabled_switch, Switch)
        self.assertIsInstance(child_3.child, NumberInput)
        self.assertIsInstance(child_4, Checkbox)

        #
        # assert that dynamics work as expected
        #

        self.assertEqual(
            {
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.75,
                "verbose": False,
            },
            view_model._get_value(),
        )

        # Simulate user clicks the "verbose" checkbox
        child_4.toggle()
        self.assertEqual(True, child_4.value)
        self.assertEqual(
            {
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.75,
                "verbose": True,
            },
            view_model._get_value(),
        )

        # Simulate user clicks the "enabled" checkbox
        child_3.child_enabled_switch.toggle()
        self.assertEqual(None, child_3.value)
        self.assertEqual(
            {
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": None,
                "verbose": True,
            },
            view_model._get_value(),
        )

        # Simulate user clicks the "enabled" checkbox once more
        child_3.child_enabled_switch.toggle()
        self.assertEqual(0.75, child_3.value)
        self.assertEqual(
            {
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.75,
                "verbose": True,
            },
            view_model._get_value(),
        )

        # Simulate user sets a new "threshold value"
        child_3.child.value = 0.25
        self.assertEqual(0.25, child_3.value)
        self.assertEqual(
            {
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.25,
                "verbose": True,
            },
            view_model._get_value(),
        )
