#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from cuiman.api.ui.uifieldinfo import UIFieldInfo
from cuiman.api.ui.uifield import UIBuilder, UIFieldFactory, UIField
from cuiman.api.ui.viewmodel import ArrayViewModel, ObjectViewModel, PrimitiveViewModel
from gavicore.models import DataType, Schema


# -----------


class Panel:
    pass


class ListEditor:
    pass


class TextField:
    pass


# -----------


class MyObjectField(UIField[ObjectViewModel, Panel]):
    def __init__(self, field_info: UIFieldInfo):
        self.field_info = field_info
        self.node = ObjectViewModel(field_info)
        self.panel = Panel()

    def get_view_model(self) -> ObjectViewModel:
        return self.node

    def get_view(self) -> Panel:
        return self.panel


class MyArrayField(UIField[ArrayViewModel, ListEditor]):
    def __init__(self, field_info: UIFieldInfo):
        self.field_info = field_info
        self.node = ArrayViewModel(field_info)
        self.view = ListEditor()

    def get_view_model(self) -> ArrayViewModel:
        return self.node

    def get_view(self) -> ListEditor:
        return self.view


class MyTextField(UIField[PrimitiveViewModel[str], TextField]):
    def __init__(self, field_info: UIFieldInfo):
        self.field_info = field_info
        self.node = PrimitiveViewModel(field_info)
        self.text_field = TextField()

    def get_view_model(self) -> PrimitiveViewModel[str]:
        return self.node

    def get_view(self) -> TextField:
        return self.text_field


# -----------


class MyObjectFactory(UIFieldFactory):
    def compute_field_score(self, _ctx, field_info: UIFieldInfo) -> int:
        return 1 if field_info.schema_.type == DataType.object else 0

    def create_field(self, _ctx, field_info: UIFieldInfo) -> UIField:
        return MyObjectField(field_info)


class MyArrayFactory(UIFieldFactory):
    def compute_field_score(self, _ctx, field_info: UIFieldInfo) -> int:
        return 1 if field_info.schema_.type == DataType.array else 0

    def create_field(self, _ctx, field_info: UIFieldInfo) -> UIField:
        return MyArrayField(field_info)


class MyTextFactory(UIFieldFactory):
    def compute_field_score(self, _ctx, field_info: UIFieldInfo) -> int:
        return 1 if field_info.schema_.type == DataType.string else 0

    def create_field(self, _ctx, field_info: UIFieldInfo) -> UIField:
        return MyTextField(field_info)


# -----------


def test_ui_builder():
    b = UIBuilder()
    b.register_factory(MyArrayFactory())
    b.register_factory(MyObjectFactory())
    b.register_factory(MyTextFactory())

    field_info = UIFieldInfo(
        name="root",
        layout="column",
        schema=Schema(
            type=DataType.object,
            properties={
                "datasets": UIFieldInfo(
                    name="datasets",
                    schema=Schema(
                        type=DataType.array, items=Schema(type=DataType.string)
                    ),
                ),
                "config": UIFieldInfo(
                    name="config",
                    schema=Schema(type=DataType.string),
                ),
            },
        ),
    )
    field = b.create_ui(field_info)
