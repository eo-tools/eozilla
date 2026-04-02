# Architecture

_This chapter is currently just a collection of design diagrams. Perhaps it will be of interest to some._

_Note, should the following diagram code not render, copy it 
into the [mermaid](https://www.mermaidchart.com/) editor._

## Package Dependencies

```mermaid
---
config:
    class:
        hideEmptyMembersBox: false
    theme: default
---
classDiagram
direction TD
    class appligator {
    }
    class cuiman {
    }
    class gavicore {
    }
    class procodile {
    }
    class wraptile {
    }
    cuiman ..> gavicore : uses
    appligator ..> gavicore : uses
    appligator ..> procodile : uses (opt.)
    procodile ..> gavicore : uses
    wraptile ..> gavicore : uses
    wraptile ..> procodile : uses (opt.)
```


## Core Classes

```mermaid
---
config:
    class:
        hideEmptyMembersBox: true
    theme: default
---
classDiagram
    direction TD
    namespace cuiman {
        class api.AsyncClient
        class api.Client
        class gui.Client
        class cli
    }
    namespace gavicore {
        class models
        class models.ProcessRequest
        class models.ProcessDescription
        class models.Schema
        class ui
        class ui.Field
        class ui.FieldMeta
        class ui.FieldGenerator
        class util
        class util.request.ExecutionRequest
        class service
        class service.Service
    }
    namespace wraptile {
        class server
        class routes
        class services.local.LocalService
        class services.airflow.AirflowService
    }
    namespace procodile {
        class JobContext
        class Process
        class ProcessRegistry
        class cli.new_cli
    }
    namespace appligator {
        class airflow.gen_dag
    }

    cli ..> api.Client : uses
    cli ..> ExecutionRequest
    gui.Client --|> api.Client : inherits
    api.Client ..> service.Service : uses
    api.AsyncClient ..> service.Service : uses
    service.Service ..> models : uses
    services.local.LocalService --|> service.Service : implements
    services.airflow.AirflowService --|> service.Service : implements
    routes ..> service.Service : uses
    server ..> routes : uses
    server ..> services.local.LocalService : can run with
    server ..> services.airflow.AirflowService : can run with
    services.local.LocalService ..> ProcessRegistry : uses
    airflow.gen_dag ..> ProcessRegistry : uses
    ProcessRegistry *--> Process: holds
    Process ..> JobContext : uses
    cli.new_cli ..> ExecutionRequest : uses
    models *-- models.ProcessRequest
    ExecutionRequest --|> models.ProcessRequest
    
    note for gui.Client "will later inherit from AsyncClient"

```

## Gavicore - Service Interface

Given here is the design used in package `gavicore.service`.

```mermaid
classDiagram
direction TB
    class Service {
        get_conformance()
        get_capabilities()
        get_processes()
        get_process(process_id)
        execute_process(process_id, process_request)
        get_jobs()
        get_job(job_id)
        get_job_result(job_id)
    }
    class ProcessList {
    }
    class ProcessSummary {
        process_id
    }
    class ProcessDescription {
    }
    class ProcessRequest {
        inputs
        outputs
        response
        subscriber
    }
    class JobList {
    }
    class JobInfo {
        process_id
        job_id
        status
        progress
    }
    class JobResult {
    }
    class InputDescription {
        schema
    }
    class Description {
        title
        description
    }
    ProcessList *--> ProcessSummary : 0 .. N 
    ProcessSummary --|> Description
    ProcessDescription --|> ProcessSummary
    ProcessDescription *--> InputDescription : 0 .. N by name
    ProcessDescription *--> OutputDescription : 0 .. N by name
    InputDescription --|> Description
    OutputDescription --|> Description
    JobList *--> JobInfo : 0 .. N 
    Service ..> ProcessList : obtain
    Service ..> ProcessDescription : obtain
    Service ..> JobList : obtain
    Service ..> JobInfo : obtain
    Service ..> JobResult : obtain   
    Service ..> ProcessRequest : use      
```

## Gavicore - Generating UIs

The `gavicore.ui` package contains the code to generate widgets and panels 

- from plain OpenAPI Schema instances of type `gavocore.models.Schema`, and
- from `gavicore.models.InputDescription` instances contained in
  a `gavicore.models.ProcessDescription` instance.

The `gavicore.ui` machinery is used by `cuiman.gui` to generate UIs for selected
processes.

The core framework is neutral with respect to the target UI library.
The `gavicore.ui.providers.panel` package contain a `PanelField` implementation 
that generates UIs for the [Panel](https://panel.holoviz.org/) library.

### `gavicore.ui.field` 

The machinery that can generate UIs from OpenAPI Schemas.
Entry points are `FieldGenerator` with one or more registered 
`FieldFactory` implementations:

```python
from gavivore.models import Schema
from gavivore.ui import FieldGenerator, FieldMeta

# what is needed:
# --- factories that generate fields from metadata (required)
from mylib import MyFieldFactory1, MyFieldFactory2
# --- observer for value changes in the generated UI tree (optional)
from mylib import MyViewModelObserver
# --- a top-level field metadata, e.g. from OpenAPI Schema (required)
my_schema = Schema(**{...})
my_field_meta = FieldMeta.from_schema(my_schema)
# --- an initial value for the UI (optional)
my_value = {}

# Generator setup:
generator = FieldGenerator()
generator.register_field_factory(MyFieldFactory1())
generator.register_field_factory(MyFieldFactory2())
# Generator usage:
field = generator.generate_field(my_field_meta)

# Then:
# --- populate UI fields
field.view_model.value = my_value
# --- observe value changes in UI fields
my_observer = MyViewModelObserver()
field.view_model.watch(my_observer)
# --- and do something to render field.view
```

```mermaid
---
config:
    class:
        hideEmptyMembersBox: true
    theme: default
---
classDiagram
    direction LR
    
    Field --> FieldMeta
    Field --> View
    Field --> gavicore.ui.vm.ViewModel
    FieldBase --|> Field
    FieldContext --> FieldMeta
    FieldFactory ..> Field: create
    FieldFactory ..> FieldContext: use
    FieldFactory ..> FieldContext: use
    FieldFactoryBase --|> FieldFactory
    FieldGenerator ..> FieldContext : create
    FieldGenerator --> FieldFactoryRegistry
    FieldFactoryRegistry *--> FieldFactory 

    class Field {
        meta: FieldMeta
        view_model: ViewModel
        view: Any
    }
    
    class FieldBase {
        _bind()*
    }

    class FieldMeta {
        name: str
        schema: Schema
        widget: str
        layout: FieldLayout
        order: int
        advanced: bool
        title: str
        description: str
        
        from_schema(schema)$ FieldMeta
        from_input_description(input)$ FieldMeta
        from_input_descriptions(inputs)$ FieldMeta
    }

    class FieldFactory {
        get_score(meta: FieldMeta)* int
        create_field(ctx: FieldContext)* Field 
    }

    class FieldContext {
        meta: FieldMeta
        vm: ViewModelFactory
        
        create_property_fields(obj_meta) dict
        create_item_field(array_meta) Field
        create_child_field(child_meta) Field
    }

    class FieldFactoryRegistry {
        register_factory(factory) Callable
        find_factory(meta: FieldMeta) FieldFactory|None
    }

    class FieldGenerator {
        register_field_factory(factory: FieldFactory)
        generate_field(meta: FieldMeta, initial_value) Field
    }
```

### `gavicore.ui.providers.panel`

Implements `PanelField` and `PanelFieldFactory` for generating UIs 
from OpenAPI Schema targeting the [Panel](https://panel.holoviz.org/) library.

This means, the `PanelField.view` object will be a widget-like component that 
can be used as part of a larger UI developed with [Panel](https://panel.holoviz.org/).

```mermaid
---
config:
    class:
        hideEmptyMembersBox: true
    theme: default
---
classDiagram
    direction LR
    
    PanelField --|> gavicore.ui.FieldBase
    PanelField ..|> gavicore.ui.FieldMeta : use
    PanelField ..|> gavicore.ui.FieldGenerator : use
    PanelField ..|> PanelFieldFactory : register
    
    PanelFieldFactory --|> gavicore.ui.FieldFactoryBase
    PanelFieldFactory ..|> gavicore.ui.FieldContext : use
    
    class PanelField {
        from_schema(schema: Schema)$ PanelField
        from_meta(meta: FieldMeta)$ PanelField
    }
```

###  `gavicore.ui.vm` 

Defines class `ViewModel` which is used to propagate value into the UI and 
to observe value changes in the UI fields.

```mermaid
---
config:
    class:
        hideEmptyMembersBox: true
    theme: default
---
classDiagram
    direction BT

    ViewModel *--> ViewModelObserver 
    ViewModel --> gavicore.ui.FieldMeta 
    ViewModelObserver ..> ViewModelChangeEvent : use
    ViewModel ..> ViewModelChangeEvent : create
    ViewModelChangeEvent --|> ViewModelChangeEvent : causes 
    
    class ViewModel {
        meta: FieldMeta
        value: Any
        watch(observers) 
        dispose()
    }
    
    class ViewModelChangeEvent {
        source: ViewModel
        causes: ViewModelChangeEvent[]
    }
    
    PrimitiveViewModel --|> ViewModel
    CompositeViewModel --|> ViewModel
    ArrayViewModel --|> CompositeViewModel
    ObjectViewModel --|> CompositeViewModel
```

