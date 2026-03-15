
A small Python UI-generating framework:

- `UIFieldInfo` as the normalized schema/UI metadata layer
- a GUI-independent node tree
- pluggable state backends
- a view/widget registry
- an optional `param` + `panel` adapter for Jupyter notebook UIs

## Design

The core idea is:

```text
OGC API / JSON Schema / x-ui metadata
                ↓
           UIFieldInfo
                ↓
      FieldNode tree (GUI-independent)
                ↓
      State backend (plain or param)
                ↓
       View registry / renderer
```

### Why this structure

- `UIFieldInfo` stays the normalized metadata object.
- The node tree owns runtime structure and value composition.
- State is pluggable, so you are **not forced to use `param`**.
- Views are pluggable, so app developers can register custom widgets.
- `param` is an adapter, not a core dependency of the architecture.

## Package layout

- `cuiman.api.ui.field`:  `UIFieldInfo`
- `cuiman.api.ui.state`: generic state protocol + plain in-memory state
- `cuiman.api.ui.nodes`: node tree classes
- `cuiman.api.ui.builder`: builds a node tree from `UIFieldInfo`
- `cuiman.api.ui.state`: `ViewFactory`, `ViewRegistry`
- `cuiman.gui.adapters.param_state`: optional `param`-based state
- `cuiman.gui.adapters.panel_views`: example Panel widget factories


## Example

```python
from cuiman.api.ui.field import UIFieldInfo
from cuiman.api.ui.builder import NodeBuilder
from cuiman.api.ui.view import ViewRegistry
from cuiman.gui.adapters.param_state import ParamState
from cuiman.gui.adapters.panel_views import  register_default_panel_factories
from gavicore.models import DataType, Schema

root_field = UIFieldInfo(
    name="inputs",
    schema=Schema(type=DataType.object),
    children=[
        UIFieldInfo(
            name="threshold",
            title="Threshold",
            widget="slider",
            minimum=0.0,
            maximum=1.0,
            schema=Schema(type=DataType.number, default=0.5),
        ),
        UIFieldInfo(
            name="verbose",
            title="Verbose",
            widget="checkbox",
            schema=Schema(type=DataType.boolean, default=False),
        ),
    ],
)

builder = NodeBuilder(state_cls=ParamState)
root = builder.build(root_field)

registry = ViewRegistry()
register_default_panel_factories(registry)
panel_view = registry.render(root)

# In a notebook:
# panel_view.servable()

print(root.to_python())
```

## Notes

### 1. Where `x-ui` fits

The architecture assumes that `UIFieldInfo` has already been normalized from:

- OGC API process input/output descriptions
- subschemas
- `x-ui` objects
- prefixed extension fields like `x-ui:widget`

That means widget selection must not rely only on JSON schema. Factories can inspect any `UIFieldInfo` fields:

- `widget`
- `title`
- `description`
- `tooltip`
- `group`
- `advanced`
- `minimum` / `maximum`
- custom extension fields stored in `model_extra`

### 2. Why the node owns state, but not necessarily Param

The node tree always owns state through a small state protocol. That gives you:

- a consistent place to read/write values
- easier serialization to Python values / Pydantic objects
- replaceable renderers

But the state object itself is pluggable. The provided implementations are:

- `PlainState`: no external dependency
- `ParamState`: wraps a `param.Parameterized` object

### 3. Why views do not create the node tree

Views are treated as adapters. They bind to node state and render widgets. 
This keeps the core model independent from Panel, Param, CLI, or any other
UI framework.

Custom widgets are added by registering additional factories in 
the `ViewRegistry`.
