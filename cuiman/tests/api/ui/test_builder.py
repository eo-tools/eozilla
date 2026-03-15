from cuiman.api.ui.builder import NodeBuilder
from cuiman.api.ui.field import UIFieldInfo

from cuiman.gui.adapters.param_state import ParamState
from gavicore.models import Schema, DataType


def test_build_and_serialize_object_tree_plain():
    root_field = UIFieldInfo(
        name="inputs",
        schema=Schema(type=DataType.object),
        children=[
            UIFieldInfo(name="a", schema=Schema(type=DataType.number, default=1.5)),
            UIFieldInfo(name="b", schema=Schema(type=DataType.boolean, default=True)),
        ],
    )

    root = NodeBuilder().build(root_field)
    assert root.to_python() == {"a": 1.5, "b": True}


def test_build_and_serialize_object_tree_param():
    root_field = UIFieldInfo(
        name="inputs",
        schema=Schema(type=DataType.object),
        children=[
            UIFieldInfo(name="a", schema=Schema(type=DataType.number, default=1.5)),
            UIFieldInfo(name="b", schema=Schema(type=DataType.boolean, default=True)),
        ],
    )

    root = NodeBuilder(state_cls=ParamState).build(root_field)
    assert root.to_python() == {"a": 1.5, "b": True}
