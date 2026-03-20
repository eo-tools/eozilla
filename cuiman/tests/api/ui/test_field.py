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
from cuiman.api.ui.vm import ViewModel, ObjectViewModel
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


class NumberComponent(Component):
    pass


class NullableComponent(Component):
    pass


# --- UI field adapters --------


class MyObjectField(UIFieldBase):
    def __init__(
        self,
        ctx: UIBuilderContext,
    ):
        super().__init__(ctx.field_meta)
        child_fields = ctx.create_child_fields()
        view_models = {k: f.get_view_model() for k, f in child_fields.items()}
        views = {k: f.get_view() for k, f in child_fields.items()}
        self._view_model = ctx.vm.object(
            property_view_models=view_models,
        )
        self._panel_component = PanelComponent(views=views)

    def get_view_model(self) -> ViewModel:
        return self._view_model

    def get_view(self) -> PanelComponent:
        return self._panel_component


class MyArrayField(UIFieldBase):
    def __init__(self, ctx: UIBuilderContext):
        super().__init__(ctx.field_meta)
        self._view_model = ctx.vm.array()
        self._list_editor_component = ListEditorComponent()

    def get_view_model(self) -> ViewModel:
        return self._view_model

    def get_view(self) -> ListEditorComponent:
        return self._list_editor_component


class MyTextField(UIFieldBase):
    def __init__(self, ctx: UIBuilderContext):
        super().__init__(ctx.field_meta)
        self._view_model = ctx.vm.primitive()
        self._text_component = TextComponent()

    def get_view_model(self) -> ViewModel:
        return self._view_model

    def get_view(self) -> TextComponent:
        return self._text_component


class MyNumberField(UIFieldBase):
    def __init__(self, ctx: UIBuilderContext):
        super().__init__(ctx.field_meta)
        self._view_model = ctx.vm.primitive()
        self._number_component = NumberComponent()

    def get_view_model(self) -> ViewModel:
        return self._view_model

    def get_view(self) -> NumberComponent:
        return self._number_component


class MyNullableField(UIFieldBase):
    def __init__(self, ctx: UIBuilderContext):
        super().__init__(ctx.field_meta)
        non_nullable_meta = ctx.field_meta.to_non_nullable()
        non_nullable_field = ctx.create_child_field(non_nullable_meta)
        non_nullable_view_model = non_nullable_field.get_view_model()
        non_nullable_view = non_nullable_field.get_view()
        self._view_model = ctx.vm.nullable(
            non_nullable_view_model=non_nullable_view_model
        )
        self._number_component = NullableComponent(non_nullable_view=non_nullable_view)

    def get_view_model(self) -> ViewModel:
        return self._view_model

    def get_view(self) -> NumberComponent:
        return self._number_component


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


class MyStringFactory(UIFieldFactoryBase):
    def get_string_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_string_field(self, ctx: UIBuilderContext) -> UIField:
        return MyTextField(ctx)


class MyNumberFactory(UIFieldFactoryBase):
    def get_number_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_number_field(self, ctx: UIBuilderContext) -> UIField:
        return MyNumberField(ctx)


class MyNullFactory(UIFieldFactoryBase):
    def get_null_score(self, field_meta: UIFieldMeta) -> int:
        return 1

    def create_null_field(self, ctx: UIBuilderContext) -> UIField:
        return MyNullableField(ctx)


# --- UI field builder usage --------


class UIFieldBuilderTest(TestCase):
    def test_builder(self):
        b = UIFieldBuilder()
        b.register_factory(MyArrayFactory())
        b.register_factory(MyObjectFactory())
        b.register_factory(MyStringFactory())
        b.register_factory(MyNumberFactory())
        b.register_factory(MyNullFactory())

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
        self.assertIsInstance(field, MyObjectField)
        view_model = field.get_view_model()
        view = field.get_view()
        self.assertIsInstance(view_model, ObjectViewModel)
        self.assertIsInstance(view, PanelComponent)
