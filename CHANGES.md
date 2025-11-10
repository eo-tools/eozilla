## Changes in version 0.0.8 (in development)

- Added `get_default()` and `set_default()` class methods to 
  `cuiman.ClientConfig` to allow for customizing the default values  
  for the client configuration.
- Added `new_cli()` to both `cuiman.cli` and `wraptile.cli` packages 
  which allows for creating customized CLIs. 
  The customization options are `name`, `help`, `summary`, `version`. 
- Updated architecture diagrams in `docs/architecture.md`.
- Added `click` as dependency to `gavicore` as it is explicitly imported.
- `gavicore.util.request.ExecutionRequest` no longer raises 
  `click.ClickException` but `ValueError`. (#19)

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
