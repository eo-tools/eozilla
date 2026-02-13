# Workflow Development

A workflow defines how multiple python functions are connected and executed together.
Each workflow has exactly one main process and any number of dependent steps.
Steps may consume outputs from the main process or from other steps.

Workflows are acyclic and are executed in topological order based on declared
dependencies.

From an OGC API – Processes (Part 3 draft) perspective:

- A workflow behaves like a single process by exposing itself as a process.
- Internally, it is a directed acyclic graph (DAG) of sub-processes
- Each workflow step is itself a [valid](#dependency-validation) process
- Outputs from one step may be consumed as inputs by another step

Workflows allow complex execution graphs to be expressed declaratively while
remaining compliant with the OGC process model.

## Conceptual Model (OGC Alignment)

| Concept         | Meaning                                                                                                                                             |
|-----------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| Workflow        | A directed, acyclic graph of processes with a single main entry point and a single output, where all data dependencies are explicitly declared.     |
| Main step       | The primary entrypoint declared using `registry.main()`                                                                                             |
| Step            | A sub-process within the workflow, defined using `your_process.step()` where `your_process` is the python function decorated with `registry.main()` |
| Dependency      | A data relationship between process inputs and outputs                                                                                              |
| Execution order | A topologically sorted process graph                                                                                                                |

A workflow must:

- Define exactly one main entrypoint
- Define exactly one output step
- Contain no cycles
- Explicitly declare all inter-process dependencies

## WorkflowRegistry — Conceptual Overview

### Motivation

[OGC API – Processes Part 3 (draft)](https://docs.ogc.org/DRAFTS/21-009.html)
introduces the concept of workflows, where a process execution request may reference
other processes as inputs (“nested processes”).
This enables clients to define ad-hoc workflows dynamically at execution time.

This framework (`procodile`) takes a complementary approach:

    Instead of defining workflows dynamically in JSON at execution time, workflows 
    are authored declaratively in Python, registered once, and then exposed as 
    standard OGC processes.

Internally, workflows are represented as structured Python objects (`Workflow`) that
capture:

- step definitions
- input bindings (`FromMain`, `FromStep`)
- execution order
- execution logic (`workflow.run`)


| Aspect           | OGC Nested Processes | Procodile Workflow Framework |
|------------------|----------------------|------------------------------|
| Definition order | Leaf-first           | Root-first                   |
| Representation   | Nested JSON          | Explicit DAG                 |
| Primary use      | Ad-hoc execution     | Deployment & reuse           |
| Identity         | Execution-scoped     | Stable process ID            |
| Execution model  | Tree evaluation      | DAG execution                |

Both models describe the same execution semantics

The framework is the inverse authoring model of nested processes

Future support for nested execution requests can be added without changing the internal
model

### Why Workflows are exposed as Processes

OGC API – Processes is fundamentally process-centric:

- Clients discover `/processes`
- Clients execute `/processes/{id}/execution`

There is no separate “workflow” resource in Part 1 or Part 3.

Therefore:

    A workflow must be represented as a process in order to be OGC-compliant.

The `ProcessRegistry` provides this abstraction by projecting workflows into
processes.

`ProcessRegistry` is a mapping-like registry that:

- stores internal `Workflow` objects
- exposes them externally as `Process` objects

### Future Compatibility with Nested Execution Requests

Although workflows are currently authored as Python objects, the internal representation
already contains everything needed to support OGC Part 3 nested execution requests in
the future.

A future extension may:

- accept nested execution JSON
- translate it into an internal workflow DAG
- execute it using the same runtime
- or deploy it as a persistent workflow

In that scenario:

- nested execution becomes an alternative front door
- the internal execution model remains unchanged

This ensures forward compatibility with the OGC API – Processes Part 3 draft.

## Creating a Workflow

Workflows are created through a `WorkflowRegistry`.

```python
from procodile import ProcessRegistry

registry = ProcessRegistry()
```

Each workflow is uniquely identified by its `id`.

## Defining the Main Step

The main step represents the workflow’s external interface. It is the only step that
receives user-supplied inputs.

Every workflow must define exactly one main step.

For e.g.,

```python
@registry.main(
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

Workflow steps are defined using the `@main_step.step` decorator.

Each step is a process that may depend on:

- Outputs from the main step
- Outputs from other workflow steps

```python
@main_step.step(id="second_step")
def second_step(id: str) -> str:
    return id[::-1]
```

## Declaring Dependencies

Dependencies are either declared

- using `typing.Annotated` in type annotations of your function argument declarations or
- using `pydantic.Field` in the decorator's `inputs` and `outputs` values.

### From the Main Step

Use `FromMain` to reference outputs of the main step.

```python
from typing import Annotated
from procodile import FromMain

@main_step.step(id="use_main")
def use_main(
    id: Annotated[str, FromMain(output="a")]
) -> str:
    return id
```

or

```python
from typing import Annotated
from procodile import FromMain
from pydantic import Field

@main_step.step(
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
from procodile import FromStep

@main_step.step(id="use_step")
def use_step(
    value: Annotated[str, FromStep(step_id="second_step", output="return_value")]
) -> str:
    return value
```

or

```python
from procodile import FromStep

@main_step.step(id="use_step", 
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
from procodile import FromStep, FromMain

@main_step.step(id="mixed_step")
def mixed_step(
    a: Annotated[str, FromMain(output="a")],
    b: Annotated[str, FromStep(step_id="second_step", output="return_value")],
) -> str:
    return f"{a}:{b}"
```

or

```python
from procodile import FromStep, FromMain

@main_step.step(
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
@main_step.step(
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

- Exactly one main step
- Exactly one output step (leaf step) -> this returns the final output
- Referenced steps must exist
- Referenced outputs must exist
- Cyclic dependencies are rejected

Errors are raised immediately if the workflow is invalid.

## Execution Order

Execution order is automatically derived using topological sorting.

To ensure seamless integration with orchestrating engines
(such as Apache Airflow or local runners), the system automatically
appends a final step (`procodile.workflow.FINAL_STEP_ID`) to every user-created
workflow.

The final step serves as a standardized exit point for data. By maintaining a
consistent final node, orchestrators can reliably extract the workflow's
output without needing to parse unique or variable step names defined by
the user.

**Important**: The final step node is a passthrough entity. It does not perform any data
transformations, computations, or logic. Its sole responsibility is to
receive the output from the preceding step and expose it via a standardized
key.

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
