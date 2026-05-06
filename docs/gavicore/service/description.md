# `gavicore.service` Description


## Overview

This package defines the core interface [Service][gavicore.service.Service] 
which is an abstraction of the Wraptile server's backend implementation.

The following class diagram provides an overview of how 
[Service][gavicore.service.Service] relates to other model classes defined in 
Gavicore.


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
