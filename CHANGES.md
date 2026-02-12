## Changes in version 0.0.9 (in development)

### Enhancements

The following enhancements have been applied to the main panel in `cuiman.gui.panels`:
  - Added functional "Get Results" button
  - Moved not-yet-functional process request file actions into a custom drop-down-menu.
  - Added preliminary output GUI to the main panel.
    Only shown, if multiple output values are used. The UI is still 
    experimental and subject to change. (#36)
  - Added switch "Show advanced inputs". 
  - Fixed updating job details display.
- Added tooltips to GUI widgets that support it in the `cuiman` GUI client.
  Tooltip texts are taken from the process input `description` metadata.
- Added `cuiman` dependency `pydantic-settings` introduced in version 0.0.8. (#53)
- By using `inputs` and `outputs` keyword arguments of 
  `procodile.ProcessRegistry.process()` it is now possible to also provide 
  `gavicore.models.InputDescription` and `gavicore.models.OutputDescription` 
  that are merged into the input and output descriptions of the process.
  Also added helper function `procodile.additional_parameters()`. (#46)
- Provided additional options to customize `cuiman`:
  - Use `cuiman.ClientConfig` class as base class and then configure it with a custom 
    `pydantic_settings.SettingsConfigDict` instance.
  - Override class members in `cuiman.ClientConfig` to initialize custom default values,
    override model classes, and implement application-specific behaviour.
  - Create a dedicated CLI instance with customized settings.
  - The `show()` method of the `cuiman.gui.Client` now supports passing application-
    specific parameters, e.g., to filter processes and process inputs. 
- Added a couple of common authentication methods to `cuiman` client API and CLI 
  configuration (via command `configure`): basic, login, token, api-key methods are 
  now supported.
- Updated documentation.
- `Workflow Orchestration Support`: You can now define Python functions as 
  individual processes and link them using explicit dependencies defined using 
  `steps`. This allows for the creation of complex, executable workflows 
  directly within `procodile`. (#50)
- Updated `appligator` to generate Airflow DAGs directly from a
  `WorkflowRegistry`, supporting workflows with multiple, explicitly defined
  steps.
- Added a new `--image-name` option to the `appligator` CLI to control the
  Docker image used for generated Airflow tasks.
- Introduced an **Intermediate Representation (IR)** layer that normalizes
  workflows from `WorkflowRegistry` before DAG generation, enabling easier 
  debugging, clearer dependency inspection, and more robust and extensible 
  DAG rendering.
- Enhanced and updated documentation.

### Fixes

- Fixed problem where the GUI client's `show_jobs()` showed an empty panel
  although jobs are shown by `get_jobs()`. (#35) 
- No longer showing "No job selected" in the GUI client's main panel.
  If no job given, the job info panel is now hidden.
- Removed persistent error message in GUI client's job info panel.
- Fixed `gavicore.util.schema.inline_schema_refs` crashing on schemas with 
  `additionalProperties: false` (e.g., Pydantic models using `extra="forbid"`).

### Other changes

- Refactored panels in `cuiman.gui.panels` package to follow MVVM 
  (Model–View–ViewModel) style.
- Renamed `gavicore.util.schema.create_json_schema` into `create_schema_dict`.
- Removed `gavicore.util.schema.create_schema_instance` with no replacement.


### Breaking Changes

- Renamed `input_fields` and `output_fields` keyword arguments into 
  `inputs` and `outputs` of `procodile.ProcessRegistry.process()` decorator.
- Removed `wraptile.services.local_service.LocalService.process()` decorator.
  Instead, use the `process_registry` of `LocalService` directly.
- The legacy `@process` decorator is no longer exposed. It has been 
  superseded by `@process_registry.main()` and `@your_func.step()` where 
  `your_func` is the function decorated by `@process_registry.main()`. All API 
  refinements including renamed arguments and registry access via 
  `LocalService` are now implemented within this new workflow orchestration 
  system.

## Changes in version 0.0.8

- Added `get_default()` and `set_default()` class methods to 
  `cuiman.ClientConfig` to allow for customizing the default values  
  for the client configuration.
- Added `new_cli()` to both `cuiman.cli` and `wraptile.cli` packages 
  which allows for creating customized CLIs. 
  The customization options are `name`, `help`, `summary`, `version`. 
- Renamed `procodile.cli.get_cli()` into `new_cli()` to make it consistent 
  with the `cuiman.cli` and `wraptile.cli` packages. 
- Updated architecture diagrams in `docs/architecture.md`.
- Added `click` as dependency to `gavicore` as it is explicitly imported.
- `gavicore.util.request.ExecutionRequest` no longer raises 
  `click.ClickException` but `ValueError`. (#19)
- Moved all `src/tests` folders one level up.

## Changes in version 0.0.7

- Fixed: `cuiman` cannot be imported if `ìpython` is not installed. (#13)
- Increased code coverage by a new test.

## Changes in version 0.0.6

First release on PyPI.

## Changes in version 0.0.5

- `cuiman` clients persist configuration  
  in `~/.eozilla` rather than `./s2gos`.
- `cuiman` clients read configuration from 
  environment variables names 
  starting with `EOZILLA_` rather than `S2GOS_`.
- Python package name changes:
    - renamed `s2gos_common` into `gavicore` 
    - renamed `s2gos_client` into `cuiman` 
    - renamed `s2gos_server` into `wraptile` 
    - renamed `s2gos_app_ex` into `procodile_example` 
- Created empty package `appligator` as starting point
- Extracted new package `procodile` from `gavicore`
- Initial folder name changes:
    - renamed `s2gos-dev` GH org references into `eo-tools`
    - renamed `s2gos-controller` GH org references `eozilla`
    - renamed `s2gos-common` directory into `gavicore`
    - renamed `s2gos-client` directory into `cuiman`
    - renamed `s2gos-server` directory into `wraptile`
    - renamed `s2gos-airflow` directory into `eozilla-airflow`
    - renamed `s2gos-app-ex` directory into `procodile-example`
  
- Started from `https://github.com/s2gos-dev/s2gos-controller`, which will 
  from now on use the Eozilla tools and frameworks.
