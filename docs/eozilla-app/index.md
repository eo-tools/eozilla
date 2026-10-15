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

Applications can set `ClientConfig.display_name` to brand notebook launch links,
browser debug messages, and server-reported launch errors. The browser app uses
the neutral label “Processing Service” for the service configured by the Python
client, and neutral fallback errors when branding is unavailable during startup.
See [Cuiman customization](../cuiman/customization.md) for configuration examples.

Python callers can set `ClientConfig.branding` to supply a title, favicon, and
header emoji or image. Explicit local images are served through Cuiman's
authenticated favicon and icon endpoints, so they need not be copied into the
browser build. Missing local images leave the app defaults in place. See
[browser branding and local images](../cuiman/customization.md#browser-branding-and-local-images).

## Runtime configuration

The browser loads optional `./config.json` before rendering. A standalone
deployment can add or replace this file beside `index.html` without rebuilding
the app. For Vite development, put it in `public/config.json`; Vite copies it
into the production build. The file may contain `branding`, `service`, or both:

```json
{
  "branding": {
    "title": "Sen4CAP",
    "favicon": "./assets/favicon.svg",
    "icon": {"url": "./assets/logo.svg"}
  },
  "service": {
    "apiUrl": "https://api.example.org/",
    "authType": "oauth2",
    "oauth2Protocol": "oidc",
    "authorizationServerUrl": "https://auth.example.org/",
    "clientId": "sen4cap-browser"
  }
}
```

Deploy referenced image files as well. Relative image URLs resolve against the
browser-visible app URL, including any Jupyter proxy prefix. Leading `/` URLs
are origin-relative; external URLs also work. The header icon accepts exactly
one of `{"emoji":"🌍"}` or `{"url":"..."}`. Missing or null branding fields
fall back individually to title `Eozilla`, favicon `./eozilla-small.svg`, and
header emoji `🦖`.

HTTP 404 means the optional file is absent. Other HTTP failures, network errors,
invalid JSON, and invalid settings produce a startup error. Configure static
hosting to return a real 404 for a missing JSON file rather than its SPA HTML.
The loader requests configuration with `cache: "no-store"`.

In Cuiman mode, the launch exchange completes first, then the browser reads
Python's session-authenticated configuration. Python supplies all effective
branding and service settings; a `service` entry in the JSON is ignored. The
browser continues to use Cuiman's service proxy and session cookie. Branding
query parameters do not override runtime settings.

Branding and service-default `VITE_*` environment variables are no longer used.
Version/build metadata remains build-time configuration. Existing presentation
and launch parameters (`compact`, `debug`, `scheme`, `launch`, `cuiman`, `ws`,
and `proxy`) retain their behavior. See
[standalone service configuration](service-provider.md#standalone-runtime-service-configuration)
for connection precedence and authentication.

## Further Reading

- [Cuiman App guide](../cuiman/guides/app.md) walks through launching the App,
  running a process, and updating its inputs from a notebook.
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
