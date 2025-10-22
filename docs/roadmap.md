# S2GOS Controller Roadmap

Given here are the features and issues that are worked on and will be addressed next.

## Doing

### General design

- Clarify data i/o, formats, and protocols (also check OGC spec):
    - user files --> **scene generator** --> OBJ
    - OBJ --> **scene simulator** --> Zarr 

### Airflow Service

- Test the Airflow-based service that connects to the Airflow web API
- Generate DAGs for containerized processes in Docker
- Generate DAGs for containerized processes in K8s

## Next

### GUI Client

- ❌ Bug in `show()` with bbox. To reproduce with local service
  select process `simulate_scene`: if no bbox selected, 
  client receives an error. 

### Authentication

* Implement basic authentication using OAuth2 from FastAPI, 
  use user_name/access_token from ClientConfig in
    - client 
    - server

### Authorisation

* Define roles & scopes
* Implement accordingly in
    - client 
    - server

## Backlog

### Code generation

The output of `generators/gen_models` is not satisfying: 

- Consider code generation from templates with `jinja2`
- Use [openapi-pydantic](https://github.com/mike-oakley/openapi-pydantic)
    - Use `openapi_pydantic.Schema`, `openapi_pydantic.Reference`, etc. in generated code
    - Use `openapi_pydantic.OpenAPI` for representing `s2gos/common/openapi.yaml` in 
      the generators

### Local and Airflow Service

- Path `/`:
    - Also provide a HTML version, support mimetype `text/html`

### Enhance the GUI Client

- Use the async API client version in the GUI Client.
  `panel` widget handler that use the client can and should be async.
- `show()` - show the main form where users can select a process 
  and submit process requests with inputs and outputs
    - Actions
      - open request 
        - save request 
        - save-as request
        - show success/failure
    - optional enhancements
        - integrate job status panel
        - show request as JSON
- `show_jobs()` - show all jobs in a table and provide actions on job selection: 
    - Actions:
        - ♻️️ restart dismissed/failed job(s)
- `show_processes()` - get a nicely rendered overview of all processes 
- `show_process(process_id: str = None, job_id: str = None, editable: bool = True)`


## Done

### Repo/package setup

* **DONE** Setup CI with `pixi`
    - **DONE** pixi run sync-versions
    - **DONE** pixi run generate
    - **DONE** pixi run coverage
* **DONE** Move all source code into `src` folder.
* **DONE** Use either `uv` or `pixi` for package and environment management. <-- We use `pixi`
* **DONE**: We need three main packages in the end to avoid naming clashes:
    - `s2gos_client` (now `s2gos.client`)
    - `gavicore` (now `s2gos.common.models`)
    - `s2gos_server` (now `s2gos.server`)
* **DONE**: Find out and decide how to setup GitHub repo(s) for this
    - One repository with all three packages in `src`
    - One repository with three subdirectories  <-- This is the one!
    - Three repositories 
* **DONE**: Align `ruff` settings with other [S2GOS repos](https://github.com/eo-tools).

### General design

- **DOING**: We need two API client versions: sync and async
    - **DONE**: Generate `AsyncClient`, next to `Client` 
    - **DONE**: Generate them using [`httpx`](https://github.com/encode/httpx), which 
      should replace currently used `requests`

### Processor Containerization

- Develop a simple processor development framework that
    - **DONE**: provides a CLI to query and execute processes   
    - **DONE**: supports registration of processes from python functions  
    - **DONE**: supports progress reporting by subscriber callback URLs 

### Implement CLI commands

- **DONE**: `list-processes`
- **DONE**: `get-process process_id`
- **DONE**: `list-jobs`
- **DONE**: `get-job job_id`
- **DONE**: `dismiss-job job_id`
- **DONE**: `get-job-results job_id --output <path>` 

### Enhance the GUI Client

- `show()` - show the main form where users can select a process 
  and submit process requests with inputs and outputs
  - **DONE**: select process
    - **DONE**: render input widgets
    - **DONE**: submit request
    - Actions
        - **DONE**: execute request 
        - **DONE**: get request 
- `show_jobs()` - show all jobs in a table and provide actions on job selection: 
    - **DONE**: use `Tabulator`
    - **DONE** Add an action row with actions applicable to the current table selection
    - Actions:
        - **DONE**: cancel accepted/running job(s)
    - **DONE**: delete successful/dismissed/failed job(s)
    - **DONE**: get job result(s)
- `show_job(job_id: str)` - show a dedicated job

### Local service

- **DONE**: Implement local service that can invoke any Python function
- Endpoint path `/`:
  - **DONE**: The landing page provides links to the:
    * **DONE**: The APIDefinition (no fixed path),
    * **DONE**: The Conformance statements (path `/conformance`),
    * **DONE**: The processes metadata (path `/processes`),
    * **DONE**: The endpoint for job monitoring (path `/jobs`).
  - **DONE**: Links should be absolute URL, hence we need `request: Request` as 1st function arg

### Airflow Service

- **DONE**: Implement Airflow gateway service using the Airflow API

### Error handling

* **DONE**: Include server traceback on internal server errors with 500 status
* **DONE**: We currently have only little error management in client. 
  Handle ClientError so users understand what went wrong:
  - **DONE**: Python API
  - **DONE**: CLI
  - **DONE**: GUI

### Code generation

Because the output of `generators/gen_models` is not satisfying: 

- **DONE**: Many generated classes are `RootModels` which are inconvenient for users, e.g.,
  `Input` requires passing values with `root` attributes.
- **DONE**: Basic openAPI constructs like `Schema` or `Reference` should not be  
  generated but reused from predefined `BaseModel`s.
- **DONE**: JSON generated from models is too verbose. Avoid including `None` fields and 
  fields that have default values.
- **DONE**: Generated class names like `Exception` clash with predefined Python names.
- **DONE**: Some generated class names are rather unintuitive, e.g., 
   `Execute` instead of `Request`.
- **DONE**: Adjust `s2gos/common/openapi.yaml` to fix the above and/or
- **DONE**: Configure `datamodel-code-generator` to fix the above and/or
