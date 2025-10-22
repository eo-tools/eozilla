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


