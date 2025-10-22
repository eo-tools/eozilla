# Architecture

_Note, should the following diagram code not render, copy it 
into the [mermaid](https://www.mermaidchart.com/) editor._

## Overview

```mermaid
---
config:
    class:
        hideEmptyMembersBox: true
    theme: default
---
classDiagram
direction LR
    namespace cuiman {
        class api.AsyncClient
        class api.Client
        class gui.Client
        class cli
    }
    namespace gavicore {
        class models
        class service.Service
    }
    namespace wraptile {
        class server
        class routes
        class services.local.LocalService
        class services.airflow.AirflowService
    }

    cli ..> api.Client : use
    gui.Client ..|> api.Client : inherits
    api.Client ..> service.Service : uses
    api.AsyncClient ..> service.Service : uses
    service.Service ..> models : uses
    services.local.LocalService --|> service.Service : implements
    services.airflow.AirflowService --|> service.Service : implements
    routes ..> service.Service : uses
    server ..> routes : uses
    server ..> services.local.LocalService : can run with
    server ..> services.airflow.AirflowService : can run with
    
    note for gui.Client "will later inherit from AsyncClient"
```

## S2GOS Client - GUI

Given here is the design used in package `cuiman.gui.component`.
The package contains the code to generate widgets and panels from the 
JSON schema `gavicore.models.InputDescription` instances contained in
a `gavicore.models.ProcessDescription` instance.

The `ComponentContainer` maps every `InputDescription` to a visual 
`Component` that is created for a given JSON schema.  

```mermaid
---
config:
  class:
    hideEmptyMembersBox: true
  layout: elk
---
classDiagram
direction LR
    class models.InputDescription {
      title
      description
      schema
    }
    class ComponentContainer {
	    \_\_init\_\_(input_descriptions)
      get_components()
      get_viewables()
    }
    ComponentContainer ..> ComponentFactoryRegistry : use
    ComponentContainer o--> models.InputDescription : 1..n by name
    ComponentContainer o--> Component : 1..n
    ComponentFactory ..> Component : create
    ComponentFactoryRegistry *--> ComponentFactory
```

A suitable `ComponentFactory` is selected for a given JSON schema
and will create the `Component` when it is needed.
The possible `ComponentFactory` instances are registered in a
 `ComponentFactoryRegistry` singleton.

```mermaid
---
config:
  class:
    hideEmptyMembersBox: true
  layout: dagre
---
classDiagram
direction TB
    class panel.viewable.Viewable {
	    \_\_panel\_\_()
    }
    class Component {
	    viewable
	    json_codec
	    _get_value_()
	    _set_value_(val)
	    _watch_value_(cb)
    }
    class WidgetComponent {
    }
    class ComponentFactory {
	    _accept_(schema)
	    _create_component_(schema)
    }
    class ComponentFactoryRegistry {
      register_factory(factory, type, format)
      find_factory(schema)
    }
    class ComponentFactoryBase {
	    type
	    format
	    accept(schema)
    }
    class BooleanCF {
    }
    class IntegerCF {
    }
    class NumberCF {
    }
    class StringCF {
    }
    class DateCF {
    }
    class BboxCF {
    }
    Component <|-- WidgetComponent
    Component --> panel.viewable.Viewable : 1 
    ComponentFactory ..> Component : create
    ComponentFactoryRegistry *--> ComponentFactory : 0..N
    ComponentFactory <|-- ComponentFactoryBase
    ComponentFactoryBase <|-- BooleanCF
    ComponentFactoryBase <|-- IntegerCF
    ComponentFactoryBase <|-- NumberCF
    ComponentFactoryBase <|-- StringCF
    ComponentFactoryBase <|-- DateCF
    ComponentFactoryBase <|-- BboxCF
```

## S2GOS Common

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

## Code generation

```mermaid
---
config:
  theme: default
---
flowchart LR
    openapi@{ shape: lean-r, label: "OpenAPI.yaml" }
    sync_client@{ shape: stadium, label: "cuiman.api.Client" }
    async_client@{ shape: stadium, label: "cuiman.api.AsyncClient" }
    models@{ shape: stadium, label: "gavicore.models.*" }
    service@{ shape: stadium, label: "gavicore.service.Service" }
    routes@{ shape: stadium, label: "wraptile.routes" }
    openapi --> generate
    generate --> gen-client
    generate --> gen-common
    generate --> gen-server
    gen-client --> sync_client
    gen-client --> async_client
    gen-common --> models
    gen-common --> service
    gen-server --> routes
```


Generating Airflow DAGs:

```mermaid
---
config:
  theme: default
---
flowchart LR
    local_service@{ shape: stadium, label: "wraptile.services.local.testing:service" }
    dags@{ shape: stadium, label: "s2gos_airflow/dags" }
    local_service --> gen-dags
    gen-dags --> dags
```
