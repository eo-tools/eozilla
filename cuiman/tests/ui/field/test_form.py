#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Literal
from unittest import TestCase

import pytest

from cuiman.ui import (
    Field,
    FieldBase,
    FieldContext,
    FieldFactoryBase,
    FieldFactoryRegistry,
    FieldGenerator,
    FieldMeta,
)
from cuiman.ui.vm import (
    ArrayViewModel,
    NullableViewModel,
    ObjectViewModel,
    PrimitiveViewModel,
)
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


class LibuiField(FieldBase):
    def _bind(self):
        def observe_vm(_e):
            self.view.value = self.view_model.value

        def observe_view():
            self.view_model.value = self.view.value

        self.view_model.watch(observe_vm)
        self.view.watch(observe_view)


# --- Factories for field adapters --------


class ObjectFieldFactory(FieldFactoryBase):
    def get_object_score(self, ctx: FieldContext) -> int:
        return 1

    def create_object_field(self, ctx: FieldContext) -> Field:
        prop_fields = ctx.create_property_fields()
        view_models = {k: f.view_model for k, f in prop_fields.items()}
        view_model = ctx.vm.object(properties=view_models)
        if ctx.meta.layout is None:
            views = [f.view for f in prop_fields.values()]
            view = Column(*views, label=view_model.meta.title)
        else:
            views = {k: f.view for k, f in prop_fields.items()}
            view = ctx.layout(layout_views, views)
        return LibuiField(view_model, view=view)


def layout_views(
    _ctx: FieldContext,
    direction: Literal["row", "column"],
    views: list[View],
) -> Row | Column:
    if direction == "row":
        return Row(*views)
    else:
        return Column(*views)


class ArrayFieldFactory(FieldFactoryBase):
    def get_array_score(self, ctx: FieldContext) -> int:
        return 1

    def create_array_field(self, ctx: FieldContext) -> Field:
        view_model = ctx.vm.array()
        view = ListEditor(value=view_model.value, label=view_model.meta.title)
        return LibuiField(view_model, view=view)


class StringFieldFactory(FieldFactoryBase):
    def get_string_score(self, meta: FieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: FieldContext) -> Field:
        view_model = ctx.vm.primitive()
        view = TextInput(value=view_model.value, label=view_model.meta.title)
        return LibuiField(view_model, view=view)


class NumberFieldFactory(FieldFactoryBase):
    def get_number_score(self, meta: FieldMeta) -> int:
        return 1

    def create_number_field(self, ctx: FieldContext) -> Field:
        view_model = ctx.vm.primitive()
        view = NumberInput(value=view_model.value, label=view_model.meta.title)
        return LibuiField(view_model, view=view)


class BooleanFieldFactory(FieldFactoryBase):
    def get_boolean_score(self, meta: FieldMeta) -> int:
        return 1

    def create_boolean_field(self, ctx: FieldContext) -> Field:
        view_model = ctx.vm.primitive()
        view = Checkbox(value=view_model.value, label=view_model.meta.title)
        return LibuiField(view_model, view=view)


class NullFieldFactory(FieldFactoryBase):
    def get_nullable_score(self, meta: FieldMeta) -> int:
        return 1

    def create_nullable_field(self, ctx: FieldContext) -> Field:
        non_nullable_meta = ctx.meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        non_nullable_view_model = non_nullable_field.view_model
        non_nullable_view = non_nullable_field.view
        view_model = ctx.vm.nullable(inner=non_nullable_view_model)
        view = NullableWidget(
            value=ctx.initial_value,
            child=non_nullable_view,
            label=view_model.meta.title,
        )
        return LibuiField(view_model, view=view)


# --- UI field builder usage --------


class FormFactoryTest(TestCase):
    def setUp(self):
        registry = FieldFactoryRegistry()
        registry.register(NullFieldFactory())
        registry.register(ObjectFieldFactory())
        registry.register(ArrayFieldFactory())
        registry.register(StringFieldFactory())
        registry.register(NumberFieldFactory())
        registry.register(BooleanFieldFactory())
        self.form_factory = FieldGenerator(registry)

    def test_form_factory_plain(self):
        builder = self.form_factory

        meta = FieldMeta.from_schema(
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

        field = builder.generate_field(
            meta,
            initial_value={
                "ds_paths": [],
                "config_path": "my-config.yaml",
                "threshold": 0.75,
                "verbose": False,
            },
        )
        self.assertIsInstance(field, LibuiField)
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

    def test_form_factory_with_layout(self):
        meta = FieldMeta.from_schema(
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
                            "title": "Inputs",
                        },
                        "config_path": {
                            "type": "string",
                            "format": "uri",
                            "title": "Configuration",
                        },
                        "threshold": {
                            "type": "number",
                            "nullable": True,
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "default": 0.5,
                            "title": "Threshold",
                        },
                        "verbose": {"type": "boolean", "title": "Verbose logs"},
                    },
                }
            ),
        )

        field = self.form_factory.generate_field(
            meta,
            initial_value={
                "ds_paths": ["SST-20260301.nc", "SST-20260302.nc", "SST-20260303.nc"],
                "config_path": "my-config.yaml",
                "threshold": 0.3,
                "verbose": True,
            },
        )
        self.assertIsInstance(field, LibuiField)
        view_model = field.view_model
        view = field.view
        self.assertIsInstance(view_model, ObjectViewModel)
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

        self.assertEqual(
            [
                "Inputs              Configuration             ",
                "------------------- my-config.yaml______      ",
                "| SST-20260301.nc | ( |o) Threshold           ",
                "| SST-20260302.nc |       0.3_________________",
                "| SST-20260303.nc | [x] Verbose logs          ",
                "-------------------                           ",
                "[+] [-]                                       ",
            ],
            view.render().lines,
        )

    def test_form_factory_fails(self):
        meta = FieldMeta.from_schema("x", Schema(**{}))
        with pytest.raises(
            ValueError, match="no factory found for creating a UI for field 'x'"
        ):
            self.form_factory.generate_field(meta)
