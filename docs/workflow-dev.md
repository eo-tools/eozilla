# Workflow Development

A **workflow** defines how multiple processes are connected and executed together.
Each workflow has exactly **one main process** and any number of **dependent steps**.
Steps may consume outputs from the main process or from other steps.

Workflows are **acyclic** and are executed in topological order based on declared dependencies.

From an OGC API – Processes (Part 3 draft) perspective:

- A workflow **behaves like a single process**
- Internally, it is a **directed acyclic graph (DAG) of sub-processes**
- Each workflow step is itself a valid process
- Outputs from one step may be consumed as inputs by another step

Workflows allow complex execution graphs to be expressed declaratively while
remaining compliant with the process model.

Each step in a workflow (main or any steps) is a OGC API Part 1 [Process](https://eo-tools.github.io/eozilla/process-dev/#procodile.Process)

## Conceptual Model (OGC Alignment)

| Concept | Meaning |
|------|--------|
| Workflow | A nested process |
| Main step | Workflow entry process |
| Step | Sub-process within the workflow |
| Dependency | Data linkage between process outputs and inputs |
| Execution order | Topologically sorted process graph |

A workflow **must**:
- Define exactly **one main input step**
- Define exactly **one output step**
- Contain **no cycles**
- Explicitly declare all inter-process dependencies

## Creating a Workflow 

(nested-processes-> OGC API Part 3 terminology)

Workflows are created through a `WorkflowRegistry`.

```python
from procodile.workflow import WorkflowRegistry

workflow_registry = WorkflowRegistry()
workflow = workflow_registry.get_or_create_workflow(id="example_workflow")
```

Each workflow is uniquely identified by its id.

## Defining the Main Step

The main step represents the workflow’s external interface. It is the only step that receives user-supplied inputs.

Every workflow must define exactly one main step.

For e.g.,
```python
@workflow.main(
    id="main_step",
    inputs={
        "id": Field(title="Main input"),
    },
    outputs={
        "a": Field(title="Main output"),
    },
)
def main_step(id: str) -> str:
    return id.upper()
```

## Defining Workflow Steps (Sub-Processes)

Workflow steps are defined using the `@workflow.step` decorator.

Each step is a process that may depend on:

- Outputs from the main step
- Outputs from other workflow steps

```python
@workflow.step(id="second_step")
def second_step(id: str) -> str:
    return id[::-1]
```

## Declaring Dependencies

Dependencies are declared using `typing.Annotated` in type declaration of 
your input arguments or `pydantic.Field` in the decorator.

### From the Main Step

Use `FromMain` to reference outputs of the main step.

```python
from typing import Annotated
from procodile.workflow import FromMain

@workflow.step(id="use_main")
def use_main(
    id: Annotated[str, FromMain(output="a")]
) -> str:
    return id
```

or 

```python
from typing import Annotated
from procodile.workflow import FromMain
from pydantic import Field

@workflow.step(
    id="use_main",
    inputs={
        "id": Field(title="main input")
    },
)
def use_main(
    id: str
) -> str:
    return id
```

- `output` refers to a named output of the main step.
- `"return_value"` may be used when the main step has no explicit outputs defined.

### From Another Step

Use `FromStep` to reference outputs from another workflow step.

```python
from procodile.workflow import FromStep

@workflow.step(id="use_step")
def use_step(
    value: Annotated[str, FromStep(step_id="second_step", output="return_value")]
) -> str:
    return value
```

or 

```python
from procodile.workflow import FromStep

@workflow.step(id="use_step", 
               inputs={
                   FromStep(step_id="second_step", output="return_value")
               }
)
def use_step(
    value: str
) -> str:
    return value
```

- `step_id` must refer to an existing workflow step.
- `output` must match one of the step’s outputs or `"return_value"`.

### Mixing Dependencies and Inputs

A step may mix dependencies and normal inputs.

```python
from procodile.workflow import FromStep, FromMain

@workflow.step(id="mixed_step")
def mixed_step(
    a: Annotated[str, FromMain(output="a")],
    b: Annotated[str, FromStep(step_id="second_step", output="return_value")],
) -> str:
    return f"{a}:{b}"
```

or 

```python
from procodile.workflow import FromStep, FromMain

@workflow.step(
    id="mixed_step",
    inputs={
        "a": FromMain(output="a"),
        "b": FromStep(step_id="second_step", output="return_value")
    }
)
def mixed_step(
    a: str,
    b: str
) -> str:
    return f"{a}:{b}"
```

## Declaring Outputs for Steps

Steps may declare explicit outputs.

```python
@workflow.step(
    id="final_step",
    outputs={
        "result": Field(title="Final result"),
    },
)
def final_step(
    value: Annotated[str, FromStep(step_id="mixed_step", output="return_value")]
) -> str:
    return value
```

If no outputs are declared, the return value is exposed as  `"return_value"`.

### Output Resolution Rules

Workflow execution follows strict output normalization rules.
These rules apply uniformly to main and step processes.

#### 1. No output specification

```python
{"return_value": result}
```

#### 2. Tuple return value

- Values are mapped positionally to output names
- Output names must be defined in the output specification

#### 3. Dictionary return value

- Keys are mapped directly to output names
- All keys must exist in the output specification

#### 4. Single scalar value

- Treated as a single output
- Exposed as "return_value" unless outputs are explicitly defined

### Examples

```python
# No outputs declared
return 42
# → {"return_value": 42}

# No outputs declared
return (1, 2)
# → {"return_value": (1, 2)}

# Declared outputs: ("a", "b")
return (1, 2)
# → {"a": 1, "b": 2}

# Declared outputs: ("a", "b")
return {"a": 1, "b": 2}
# → {"a": 1, "b": 2}

# Declared outputs: ("c")
return {"a": 1, "b": 2}
# → {"c":{"a": 1, "b": 2}}
```

## Dependency Validation

Dependencies are validated at workflow construction time:

- Exactly one input step (main step)
- Exactly one output step (leaf step) -> this returns the final output
- Referenced steps must exist
- Referenced outputs must exist
- Cyclic dependencies are rejected


Errors are raised immediately if the workflow is invalid.

## Execution Order

Execution order is automatically derived using topological sorting.

## Visualizing the Workflow

Workflows can be visualized as a directed graph.

```python
dot = workflow.visualize_workflow()
```

This returns a Graphviz DOT representation similar to this:

```yaml
digraph pipeline {
    rankdir=LR;
    "main_step";
    "second_step";
    "main_step" -> "second_step";
}
```
