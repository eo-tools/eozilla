# Eozilla App

Eozilla App is the browser-based client for
[OGC API - Processes](https://github.com/opengeospatial/ogcapi-processes)
services. It lets users connect to a service, browse available processes,
provide process inputs, submit executions, and inspect jobs and results.

![Eozilla App interface](images/eozilla-app.png)

## Features

- Connect to OGC API - Processes services through configurable service providers.
- Browse process descriptions and submit process-execution requests.
- Review job status, outputs, results, and error tracebacks.
- Generate input forms from process schemas, including supported UI metadata.

## Launching the App

Cuiman can launch Eozilla App in a browser using its configured service
connection:

```console
cuiman show-app
```

It can also be launched programmatically from Python:

```python
from cuiman import Client

client = Client(...)
client.show_app()
```

## Further Reading

- [Service providers and services](service-provider.md) explains connection and
  authentication behavior.
- [Schema forms](schema-form.md) documents how process schemas are rendered as
  input controls.
- [Dynamic expressions](dynamic-expressions.md) describes conditional schema-form
  behavior.

## Development Workspace

For team development, Eozilla App is a separate Git repository checked out
inside the Eozilla repository:

```text
eozilla/
  eozilla-app/
```

This layout allows the app to use the local Eozilla development service and
build directly into Cuiman. See the [contribution guide](../contributing.md#cuiman-gui-changes)
for setup and development commands.

## Documentation Maintenance

`docs/eozilla-app/` is the canonical documentation for the app within this
workspace. Substantial changes to code in `eozilla-app/` must update the
relevant page here: the overview, service-provider, schema-form, or
dynamic-expression guide.
