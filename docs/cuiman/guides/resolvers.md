# Job result resolvers

An opener reads one selected target into a Python object. A resolver answers
which targets an original output describes. For example, a STAC Item describes
several Assets; resolving it gives each Asset a selectable resource with its own
link, format, roles, and ownership. A transformer can then enrich those resources
or add descendants declared by application configuration.

The current API provides resolver dispatch, resource listings, composition, and
`client.open_job_result(resource)`. Client listing and traversal methods are still
pending. This guide calls the developer contract `resolve_job_result()` directly;
the helper below is example code, not a new client method. It does not implement
pagination, capability assessment, or Catalog/Collection crawling.

## Start the testing service

Use a development checkout with `pixi install` completed. From the repository
root, keep the service running in a separate terminal:

```bash
--8<-- "examples/guides/cuiman/cli.sh:server"
```

Start Jupyter with `pixi run jl`, or use IPython in `pixi shell`. The blocks below
use top-level `await`; run them in order in one session. For a regular Python
script, run the complete maintained example instead:

```bash
--8<-- "examples/guides/cuiman/cli.sh:python-resolvers"
```

The source is [resolvers.py](https://github.com/eo-tools/eozilla/blob/main/examples/guides/cuiman/resolvers.py).
The [job result resources notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-job-result-resources.ipynb)
adds inspection of portable snapshots and ambiguous selection.

Both server and client must run on the same machine and share its filesystem.
The test processes write small CSV/text products. Use a fresh directory: they
replace files at the supplied server-side path. File URLs from another machine
are not automatically accessible. This guide creates a temporary directory and
removes it at the end, after all reads have finished.

## Connect and retrieve an original output

```python
--8<-- "examples/guides/cuiman/resolvers.py:imports"

--8<-- "examples/guides/cuiman/resolvers.py:client"

--8<-- "examples/guides/cuiman/resolvers.py:submit"

output = TemporaryDirectory(prefix="cuiman-results-")
root = Path(output.name)
client = create_client(root / "client-config.yaml")
```

`simulate_stac_item` returns two independent outputs: `result`, an inline STAC
Item, and `report`, an ordinary text Link. `submit_stac()` submits once, waits up
to 30 seconds, and retrieves results only after success. A failed/dismissed job
raises `JobResultStatusError`; exceeding the wait raises `TimeoutError`. Retain
the returned job ID rather than resubmitting to inspect the same execution.
The explicit, fresh profile path keeps a saved personal configuration from
affecting this testing-service session; the example never saves a profile.

## Resolve the Item and select an Asset

```python
--8<-- "examples/guides/cuiman/resolvers.py:discovery"

--8<-- "examples/guides/cuiman/resolvers.py:inline-call"
```

The helper supplies the original output, process/schema facts, and client
configuration through `JobResultContext`. It then uses the configured resolver
registry in priority order. `StacResolver` recognizes the inline structure
without fetching metadata or requiring PySTAC. `ValueResolver` is the fallback
for ordinary Links and arbitrary values, including null; it preserves them as
one resource rather than splitting or dereferencing them.

The flat listing contains the Item and three Assets: `data`, `report`, and
`products`. Relative Asset locations use the inline Item's absolute self link
as their base. Roles or formats absent from the producer remain unspecified.
Listings show metadata and progress locally; rendering, indexing, and selection
do not fetch additional documents. Opener/preview capabilities are `unknown`
because this developer dispatch does not yet perform client assessment.

```python
--8<-- "examples/guides/cuiman/resolvers.py:open-call"
```

The selected CSV opens as a pandas DataFrame containing one observation for
`2026-09-01`, with NDVI `0.75`. A text report or folder without a matching reader
remains inspectable in the listing. Discovery success does not guarantee access
or an opener for every row.

`resources.select()` requires exactly one loaded match. It raises
`ResourceNotFoundError` for no match and `AmbiguousResourceError` for several.
An opaque resource ID selects an exact loaded row; include Item/output ownership
when keys repeat. A resource's JSON snapshot can be saved with
`model_dump_json()` and restored with `JobResultResource.model_validate_json()`.
Credentials and live context services are kept outside that snapshot.

## Describe known folder contents through composition

The `products` Asset points to a directory without a trailing slash. An
application can declare its useful contents instead of enumerating storage:

```python
--8<-- "examples/guides/cuiman/resolvers.py:composition"

--8<-- "examples/guides/cuiman/resolvers.py:composition-call"
```

`ProductFolderResolver` reuses `StacResolver` and owns one
`FolderResourceTransformer`. Its predicate restricts the interpretation to the
two testing processes. Each `ResourceEntry` supplies a stable key and relative
location; the declared `tables` directory contains an `observations` CSV entry
with its own format and roles. The transformer retains source ancestors and
records configuration identity/revision and derived-location provenance.

The new `observations` resource opens the same CSV as the original `data` Asset.
It has a distinct selector because it follows the configured ancestry. Opening
it uses the exact supplied target without repeating the transformer. Discovery
does not scan directories, verify file existence, or inherit credentials and
format hints from the folder. Completeness describes the supplied entries,
not an exhaustive directory inventory.

The temporary registration takes priority and is removed in `finally`. It is
scoped to `GuideConfig`, so unrelated client configuration classes are unaffected.
For a permanent application extension, declare
`extra_job_result_resolvers = (ProductFolderResolver,)` on your configuration
class. See [Discovery extensions](../customization.md#discovery-extensions).

## Resolve a linked ItemCollection with a bounded loader

`simulate_stac_item_collection` returns a Link to JSON containing two dated Items.
A metadata loader fetches this description; it never reads the described CSVs:

```python
from examples.guides.cuiman.resolvers import fetch_local_metadata

--8<-- "examples/guides/cuiman/resolvers.py:linked-call"
```

Here `fetch_local_metadata` is a bounded file reader supporting only local file
URLs. For another deployment, supply a `MetadataFetcher` using its transport and
locally scoped authentication. The fetcher returns `MetadataResponse` bytes,
effective URL, and media type. `MetadataLoader` parses and caches them, then
returns an independent `MetadataDocument` containing JSON and its reference base.
Keeping the base with the value lets relative links remain correct after redirects.

Acceptance and resolution share the loader, so the printed metadata fetch count
is `1`. Relative Assets in embedded Items resolve against the ItemCollection
document. Both Items have a `data` key, so this call selects by Item ID as well.
The opened row contains date `2026-09-02` and NDVI `0.75`.

Default `DiscoveryLimits` allow 16 fetch attempts, 2 MiB per response, 100 embedded
Items, 1000 resources per stage, depth 8, and 10 seconds per fetch. Pass custom
limits to `MetadataLoader` to change them. Cached successes and failures share
the request budget; use `loader.clear()` between operations for an explicit
refresh. Transformations are recomputed, rather than stored in this cache.
Limits and malformed entries produce diagnostics and incomplete states while
preserving successful siblings. Cancellation propagates. Advertised next pages
and Catalog/Collection navigation are retained for future explicit traversal;
this initial resolver does not follow them automatically.

## Release the client and demo files

```python
await client.close()
output.cleanup()
```

If a cell fails, run this cleanup cell before restarting the session. The
complete script uses `try`/`finally` and a temporary-directory context manager.
For reader settings and custom readers, continue with the
[opener guide](openers.md); for signatures, see the [API reference](../api.md).
