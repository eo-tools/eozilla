# Gavicore

The Eozilla _Gavicore_ package is a small library that provides common
classes and functions for other Eozilla packages.

It currently comprises the following top-level packages:

- [`models`](models/description.md) - provides 
  [pydantic](https://pydantic.dev/docs/validation/latest/concepts/models/) 
  model classes for the data models used throughout the 
  OGC API - Processes Part 1: Core (`models.core`) and Part 2: Deploy,
  Replace, Undeploy (`models.dru`).
- [`service`](service/description.md) - a Python representation of the   
  OGC API - Processes Core (`service.core`) and DRU (`service.dru`)
  interfaces, with shared error helpers in `service.errors`.
- [`util`](util/description.md) - various submodules with various reusable utilities.

The implementation is organized as follows (below `gavicore/src`):

```text
gavicore/
  models/
    __init__.py
    core.py
    dru.py
  service/
    __init__.py
    core.py
    dru.py
    errors.py
```

Import model classes and service interfaces directly from their `core` or
`dru` modules. Tests mirror this structure under `gavicore/tests/models/` and
`gavicore/tests/service/`.

User interfaces generated from `InputDescription` and `Schema` models are
implemented in [Eozilla App](../eozilla-app/schema-form.md). See
[GUI Generation](../cuiman/gui-generation.md) for customization.

