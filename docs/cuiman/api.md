# Cuiman API Reference

The Cuiman Python API is provided by the `cuiman.api` package. Frequently 
used classes and functions are also made available directly through the 
`cuiman` package. 


## Client API

`Client` provides the synchronous processing API; `AsyncClient` provides the
same interface with asynchronous server calls. Server calls may raise
`ClientError` if they fail.

For concepts and first requests, see [Getting Started](getting-started.md).
See [Configuration](configuration.md) for settings and
[Authentication](authentication.md) for login, token storage, and client lifecycle.

::: cuiman.api.Client

::: cuiman.api.ClientError


## Configuration API

::: cuiman.api.ClientConfig


## Auth Configuration API

!!! warning "Warning"

    The Client Auth Configuration API is not stable and may change without 
    notice. Do not yet rely on it.

### OpenID Connect

`OidcAuthConfig` describes a public OIDC client through its issuer URL, client ID,
and optional scopes. See [Authentication](authentication.md#oidc-and-the-launched-app)
for the login flow and credential lifecycle.

::: cuiman.api.auth


## Job Result Opener API

### Job result openers

`JobResultOpener` defines how a process result is read into a Python object,
such as an xarray Dataset, a pandas or GeoPandas DataFrame, or a Pillow image.
`client.open_job_result()` selects a reader from the configured openers.
`is_usable()` checks whether an opener can run in the current environment;
`accept_job_result()` checks whether it is a candidate for the requested output
and return type. Acceptance does not guarantee successful access or reading.
`open_job_result()` performs the read and returns the resulting object.

`JobResultOpenContext` supplies the original job results, client configuration,
process description, output selection, requested Python return type, media type
override, and reader options. Its properties expose the selected output value,
normalized Link or qualified value, and effective media type. Clients construct
this context for callers and pass it to the opener's acceptance and opening methods.

`JobResultOpenerRegistry` maintains the ordered opener classes. Built-in readers
cover datasets, tables, geospatial tables, and images, subject to their optional
dependencies. Applications add their own classes through
`ClientConfig.extra_job_result_openers` or `register_job_result_opener()`;
later registrations take priority, and configuration classes have isolated
registries. See [Customization](customization.md) for application examples.

The three classes below describe the current context-based implementation.
The [Job Result Resources](job-result-resources.md) redesign will replace the
context and opener method signatures with a single resource-based contract,
shared by opening an original job output and an explicitly selected resource.

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.opener.JobResultOpenContext

::: cuiman.api.opener.JobResultOpenerRegistry

### Job result resource descriptions

`JobResultResource` describes a selected job output or a derived resource.
`JobResultResourceListing` holds loaded resources, discovery states, diagnostics,
and an optional continuation. These models are available now; client discovery
and integration with `open_job_result()` are being implemented incrementally
according to [Job Result Resources](job-result-resources.md).

Both models are frozen Pydantic snapshots. Nested JSON objects are read-only
mappings and arrays are tuples in Python; `model_dump(mode="json")` and
`model_dump_json()` produce portable JSON objects and arrays. OGC Link fields
use their wire names, including `x-options`. Resource descriptions contain no
client association, session, credential provider, or resolved runtime credentials.
Opening hints and access descriptions must contain only non-secret metadata.

`resource.has_value` distinguishes an omitted value from a present null.
`resource.with_updates(**changes)` creates a validated replacement for use in
transformers, preserving the original snapshot. Opener and preview availability
are independent under `resource.capabilities`; assessments default to `unknown`.
An `available` assessment identifies candidates and its execution runtime, without
claiming that payload access has succeeded.

Listings support local iteration, integer/slice indexing, and
`select(id=..., output_name=..., item_id=..., key=...)`. Selection returns one
loaded row, raises `ResourceNotFoundError` when none match, or raises
`AmbiguousResourceError` when several match. These errors and the supporting
metadata models are available from `cuiman.api.resources`. A match never claims
uniqueness across unloaded pages. Plain-text and notebook HTML rendering use only
loaded metadata and show incomplete, failed, empty, and deferred states.

Resource and listing JSON use `schema_version: 1`. IDs are opaque, versioned
selectors derived from output and owner identities; effective URLs are excluded
from identity so renewing a signed location preserves selection. Continuation
scope and expiry will be enforced by the discovery implementation.

::: cuiman.api.JobResultResource

::: cuiman.api.JobResultResourceListing

## App API

::: cuiman.app.App


## CLI API

::: cuiman.cli.new_cli
