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
`accept(resource, context=...)` checks whether it is a candidate for the selected
resource and return type. Acceptance does not guarantee successful access or reading.
`open(resource, context=...)` performs the read and returns the resulting object.

`JobResultContext` supplies the receiving client's configuration, requested
Python return type, effective media type override, and candidate reader options.
It is shared with resolution and transformation, where it also carries the
original output name/value, process metadata, containing-document base URI, and
bounded metadata loader/limits. Clients construct it and resolve settings
independently for each candidate. Opening-only contexts leave the original output
name/value unset; discovery requires both before I/O. An explicitly supplied null
is a valid value. Standalone discovery can omit client
configuration. Fields are frozen, and candidate options remain independent mappings.
The selected resource supplies its own link/value and format; its original
job/output description and schema remain provenance.

`client.open_job_result(job_id, output_name=...)` retains polling and normalizes
one original output without expanding STAC or selecting an Asset.
`client.open_job_result(resource)` opens exactly that resource without job lookup,
polling, or repeated discovery. Both forms share opener dispatch and support
`data_type`, `media_type`, and reader options. Strings always identify jobs.
Explicit `output_name`, `poll_interval`, or `timeout` arguments with a resource
raise `TypeError`, including explicitly supplied defaults or `None`.

`JobResultOpenerRegistry` maintains the ordered opener classes. Built-in readers
cover datasets, tables, geospatial tables, and images, subject to their optional
dependencies. Applications add their own classes through
`ClientConfig.extra_job_result_openers` or `register_job_result_opener()`;
later registrations take priority, and configuration classes have isolated
registries. See [Customization](customization.md) for application examples.

Producer hints are validated before use. Settings resolve in order from opener
defaults, resource hints, client overrides, and explicit call options. Declared
mappings merge by key; `None` clears inheritance. `context.non_secret_options`
and `context.option_sources` expose effective settings and their source.
`ResourceAccessProvider` supplies locally authorized storage access only during
reading; candidate checks acquire no credentials or payloads. See
[Customization](customization.md#opening-extensions) for the extension contract.

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.JobResultContext

::: cuiman.api.opener.JobResultOpenerRegistry

::: cuiman.api.opener.ResourceAccessProvider

### Job result resource descriptions

`JobResultResource` describes a selected job output or a derived resource.
`JobResultResourceListing` holds loaded resources, discovery states, diagnostics,
and an optional continuation. Resources can be passed to `open_job_result()` now;
client discovery is being implemented incrementally according to
[Job Result Resources](job-result-resources.md).

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

For executable examples of discovery, selection, and opening, see the
[opener guide](guides/openers.md) and [resolver guide](guides/resolvers.md).

::: cuiman.api.JobResultResource

::: cuiman.api.JobResultResourceListing

### Discovery extensions and resource transformers

The developer discovery contracts are available from `cuiman.api.resolver`.
`JobResultResolver` receives every original output value through
the same `cuiman.api.JobResultContext` used by openers. Discovery requires its
original output name and value and selects one semantic interpretation before
Link or STAC normalization. Its loader/cache and limits are shared by delegated
resolvers, transformers, and derived opener contexts. Opening preferences do not
alter discovery, and discovery never calls the storage access provider.
Concrete built-ins are available from `cuiman.api.resolver.impl`,
mirroring `cuiman.api.opener.impl`. `StacResolver` recognizes core STAC structure
without PySTAC or full schema validation. It describes embedded Items and concrete Assets, retaining
Collection/Catalog metadata and navigation without crawling descendants.
`ValueResolver` preserves an otherwise unhandled value or Link as one resource.

`JobResultResolverRegistry` manages resolver classes in precedence order, matching
the opener registry. Its default is STAC discovery followed by the generic value
resolver. `register()` validates and promotes a class without duplicates and
returns an idempotent unregister callback; `clear()` removes registered classes.
`ClientConfig.get_job_result_resolver_registry()` caches an independent registry
for each concrete configuration class. Ordinary callers continue to configure
extensions through their client configuration.

`MetadataLoader` shares bounded JSON fetches, parsed documents, failures, and the
request budget across acceptance and resolution. The fetch/parse handoff is
`MetadataFetcher` → `MetadataResponse` → `MetadataLoader` → `MetadataDocument`:
the fetcher reads bytes using the application's transport, the response carries
those bytes and their effective URL, and the loader parses and caches JSON before
returning an independent document copy to the resolver. The separate response and
document keep transport work out of resolvers and retain the reference base
alongside the parsed value. `DiscoveryLimits` bounds both fetching and resource
expansion; `DiscoveryError` carries failures that become portable diagnostics.
The fetcher owns scoped authentication and must bound reads using the requested
byte and time limits. Resolved relative references use the containing
document's effective URI, including redirects. Cache snapshots are independent;
`clear()` between operations provides an explicit refresh. Default limits are
16 requests, 2 MiB per response, 100 embedded Items, 1000 resources, depth 8,
and 10 seconds per metadata fetch. Applications can supply `DiscoveryLimits`.

`ComposedJobResultResolver` delegates to a base resolver using the same context
and then applies its ordered `ResourceTransformer` chain. Each transformer
returns replacements for one source resource; later stages receive the preceding
stage's results. Failure retains that source and successful siblings with
diagnostics. Changed descriptions discard prior capability assessments.
`FolderResourceTransformer` derives an explicitly declared subtree from
`ResourceEntry` objects without scanning storage or testing accessibility.
These objects adapt developer-supplied configuration; they do not prescribe an
external configuration format. See [Customization](customization.md#discovery-extensions)
for composition and registration.

This implementation step supplies an unfiltered flat discovery view, including
inspectable containers. Client listing/traversal, continuation routing, view
filtering, and final capability assessment are still being implemented. Item and
resource limits or advertised next pages produce explicit partial diagnostics;
the foundation does not yet issue client continuation tokens.

::: cuiman.api.resolver.JobResultResolver

::: cuiman.api.resolver.JobResultResolverRegistry

::: cuiman.api.resolver.DiscoveryLimits

::: cuiman.api.resolver.MetadataLoader

::: cuiman.api.resolver.MetadataFetcher

::: cuiman.api.resolver.MetadataResponse

::: cuiman.api.resolver.MetadataDocument

::: cuiman.api.resolver.impl.StacResolver

::: cuiman.api.resolver.impl.ValueResolver

::: cuiman.api.resolver.ComposedJobResultResolver

::: cuiman.api.resolver.ResourceTransformer

::: cuiman.api.resolver.FolderResourceTransformer

::: cuiman.api.resolver.ResourceEntry

## App API

::: cuiman.app.App


## CLI API

::: cuiman.cli.new_cli
