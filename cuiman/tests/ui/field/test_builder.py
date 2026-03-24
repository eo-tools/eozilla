#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from unittest import TestCase

import pytest

from cuiman.ui import (
    NestedObjectFactory,
    UIField,
    UIFieldBase,
    UIFieldBuilder,
    UIFieldContext,
    UIFieldFactoryBase,
    UIFieldMeta,
)
from cuiman.ui.vm import (
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
    ViewModel,
)
from cuiman.ui.vm.object import DynamicObjectViewModel
from gavicore.models import Schema

from .libui import (
    Checkbox,
    Column,
    ListEditor,
    NullableWidget,
    NumberInput,
    Row,
    Switch,
    TextInput,
    View,
)

# --- UI field adapter --------


class LibuiViewAdapter(UIFieldBase):
    """A view adapter."""


class LibuiWidgetAdapter(UIFieldBase):
    def _bind(self):
        def observe_vm(_e):
            self.view.value = self.view_model.value

        def observe_view():
            self.view_model.value = self.view.value

        self.view_model.watch(observe_vm)
        self.view.watch(observe_view)


# --- Factories for field adapters --------


class ObjectFieldFactory(UIFieldFactoryBase):
    def get_object_score(self, ctx: UIFieldContext) -> int:
        return 1

    def create_object_field(self, ctx: UIFieldContext) -> UIField:
        prop_fields = ctx.create_property_fields()
        view_models = {k: f.view_model for k, f in prop_fields.items()}
        view_model = ctx.vm.object(properties=view_models)
        views = [f.view for f in prop_fields.values()]
        view = Column(children=views)
        return LibuiViewAdapter(view_model, view=view)


class ArrayFieldFactory(UIFieldFactoryBase):
    def get_array_score(self, ctx: UIFieldContext) -> int:
        return 1

    def create_array_field(self, ctx: UIFieldContext) -> UIField:
        view_model = ctx.vm.array()
        view = ListEditor(value=view_model.value)
        return LibuiWidgetAdapter(view_model, view=view)


class StringFieldFactory(UIFieldFactoryBase):
    def get_string_score(self, meta: UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: UIFieldContext) -> UIField:
        view_model = ctx.vm.primitive()
        view = TextInput(value=view_model.value)
        return LibuiWidgetAdapter(view_model, view=view)


class NumberFieldFactory(UIFieldFactoryBase):
    def get_number_score(self, meta: UIFieldMeta) -> int:
        return 1

    def create_number_field(self, ctx: UIFieldContext) -> UIField:
        view_model = ctx.vm.primitive()
        view = NumberInput(value=view_model.value)
        return LibuiWidgetAdapter(view_model, view=view)


class BooleanFieldFactory(UIFieldFactoryBase):
    def get_boolean_score(self, meta: UIFieldMeta) -> int:
        return 1

    def create_boolean_field(self, ctx: UIFieldContext) -> UIField:
        view_model = ctx.vm.primitive()
        view = Checkbox(value=view_model.value)
        return LibuiWidgetAdapter(view_model, view=view)


class NullFieldFactory(UIFieldFactoryBase):
    def get_null_score(self, meta: UIFieldMeta) -> int:
        return 1

    def create_null_field(self, ctx: UIFieldContext) -> UIField:
        non_nullable_meta = ctx.meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        non_nullable_view_model = non_nullable_field.view_model
        non_nullable_view = non_nullable_field.view
        view_model = ctx.vm.nullable(non_nullable=non_nullable_view_model)
        view = NullableWidget(value=ctx.initial_value, child=non_nullable_view)
        return LibuiWidgetAdapter(view_model, view=view)


# --- UI field builder usage --------


class UIFieldBuilderTest(TestCase):
    def setUp(self):
        builder = UIFieldBuilder()
        builder.register_factory(NullFieldFactory())
        builder.register_factory(ObjectFieldFactory())
        builder.register_factory(ArrayFieldFactory())
        builder.register_factory(StringFieldFactory())
        builder.register_factory(NumberFieldFactory())
        builder.register_factory(BooleanFieldFactory())
        self.builder = builder

    def test_builder_ok(self):
        builder = self.builder

        meta = UIFieldMeta.from_schema(
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
                }
            ),
        )

        field = builder.create_field(
            meta,
            initial_value={
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.75,
                "verbose": False,
            },
        )
        self.assertIsInstance(field, LibuiViewAdapter)
        view_model = field.view_model
        view = field.view

        #
        # assert that UI composition is as expected
        #

        self.assertIsInstance(view_model, ObjectViewModel)
        self.assertEqual(4, len(view_model))
        self.assertEqual(
            ["ds_paths", "config_path", "threshold", "verbose"],
            list(view_model.properties),
        )
        vm_1 = view_model.properties["ds_paths"]
        vm_2 = view_model.properties["config_path"]
        vm_3 = view_model.properties["threshold"]
        vm_4 = view_model.properties["verbose"]
        self.assertIsInstance(vm_1, ArrayViewModel)
        self.assertIsInstance(vm_2, PrimitiveViewModel)
        self.assertIsInstance(vm_3, NullableViewModel)
        self.assertIsInstance(vm_4, PrimitiveViewModel)
        self.assertIsInstance(view, Column)
        self.assertIsNotNone(view.children)
        self.assertEqual(4, len(view.children))
        children = view.children
        child_1 = children[0]
        child_2 = children[1]
        child_3 = children[2]
        child_4 = children[3]
        self.assertIsInstance(child_1, ListEditor)
        self.assertIsInstance(child_2, TextInput)
        self.assertIsInstance(child_3, NullableWidget)
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

    def test_builder_ok_with_layout(self):
        builder = self.builder
        builder.register_factory(MyNestedObjectFactory())

        meta = UIFieldMeta.from_schema(
            "root",
            Schema(
                **{
                    "type": "object",
                    "x-ui:layout": {
                        "type": "row",
                        "items": [
                            "ds_paths",
                            {
                                "type": "column",
                                "items": ["config_path", "threshold", "verbose"],
                            },
                        ],
                    },
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
                            "default": 0.5,
                        },
                        "verbose": {"type": "boolean"},
                    },
                }
            ),
        )

        field = builder.create_field(
            meta,
            initial_value={
                "ds_paths": [],
                "config_path": "my-config.yaml",
            },
        )
        self.assertIsInstance(field, LibuiViewAdapter)
        view_model = field.view_model
        view = field.view
        self.assertIsInstance(view_model, DynamicObjectViewModel)
        self.assertIsInstance(view, Row)
        row_children = view.children
        self.assertEqual(2, len(row_children))
        row_child_1 = row_children[0]
        row_child_2 = row_children[1]
        self.assertIsInstance(row_child_1, ListEditor)
        self.assertIsInstance(row_child_2, Column)
        col_children = row_child_2.children
        self.assertEqual(3, len(col_children))
        col_child_1 = col_children[0]
        col_child_2 = col_children[1]
        col_child_3 = col_children[2]
        self.assertIsInstance(col_child_1, TextInput)
        self.assertIsInstance(col_child_2, NullableWidget)
        self.assertIsInstance(col_child_3, Checkbox)

    def test_builder_failing(self):
        builder = self.builder
        meta = UIFieldMeta.from_schema("x", Schema(**{}))
        with pytest.raises(
            ValueError, match="no factory found for creating a UI for field 'x'"
        ):
            builder.create_field(meta)


class MyNestedObjectFactory(NestedObjectFactory):
    def create_row_field(
        self, ctx: UIFieldContext, view_model: ViewModel, children: list[View]
    ) -> UIField:
        view = Row(children=children)
        return LibuiViewAdapter(view_model=view_model, view=view)

    def create_column_field(
        self, ctx: UIFieldContext, view_model: ViewModel, children: list[View]
    ) -> UIField:
        view = Column(children=children)
        return LibuiViewAdapter(view_model=view_model, view=view)
