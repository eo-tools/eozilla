# Job result openers

`client.get_job_results(job_id)` retrieves result values and references.
`client.open_job_result(job_id)` waits for completion and opens a selected
output using a registered opener. Cuiman includes PySTAC, Pillow, xarray, pandas, and
GeoPandas openers; each requires its corresponding optional library. The Pillow
image opener takes precedence over the dataset openers for supported images,
including PNG and JPEG, and returns a `PIL.Image.Image`. Custom openers extend
or specialize this behavior.

## Native STAC outputs

Install `cuiman[stac]` for STAC opening. The supported and verified PySTAC range
is `>=1.15.2,<1.16`; the development Pixi environment includes it. Ordinary Cuiman
imports and non-STAC readers work without PySTAC. The built-in STAC opener runs
before generic data readers; later custom registrations retain precedence.

Start the [local testing service](../../wraptile/usage.md#stac-testing-processes)
and run this from the Pixi environment:

```python
import pystac
from cuiman import Client
from gavicore.models import ProcessRequest

client = Client(api_url="http://localhost:8008", auth={"auth_type": "none"})
try:
    job = client.execute_process(
        "create_inline_stac", ProcessRequest(inputs={"item_count": 2})
    )
    items = client.open_job_result(
        job.jobID, output_name="item_collection", data_type=pystac.ItemCollection
    )
    print([item.id for item in items])  # ['scene-1', 'scene-2']
    print(items[0].assets["data"].href)
    raw = client.get_job_results(job.jobID)  # original JSON and all output names
finally:
    client.close()
```

Repeat with `create_linked_stac` to fetch the equivalent metadata through ordinary
Link outputs. `output_name="item"` returns an Item; ItemCollection embeds the
requested Items. Collection and Catalog documents also return their native
PySTAC types, and requesting Catalog accepts a Collection. A mismatched explicit
native type fails. Unknown extension fields and concrete Collection Assets are
retained; `item_assets` definitions remain separate from concrete Assets.

The opener unwraps qualified values, recognizes STAC structure or schema hints,
and considers linked JSON/GeoJSON as candidates. Ordinary inline GeoJSON,
including empty FeatureCollections, is not assumed to be STAC. Weak linked
candidates can fall back after parsing disproves STAC; strong STAC evidence or an
explicit native request makes parsing failures terminal. Missing PySTAC for a
required STAC output explains the optional dependency.

Opening reads only the selected metadata document. It does not fetch parent,
root, child, member, next-page, preview, or Asset payloads. Advertised next-page
links remain available without automatic pagination. Asset reading through the
client and transformation composition are introduced in subsequent implementation
steps.

### Metadata limits and access

ClientConfig settings `stac_metadata_max_bytes`, `stac_metadata_timeout`, and
`stac_metadata_max_requests` default to 2 MiB of decoded bytes per document,
10 seconds per fetch, and 16 requests per opening operation, including redirects.
Limits are enforced during streamed reads; documents are never silently truncated.
HTTP and local files (native Windows paths and file URIs with spaces) are
supported metadata sources. Remote storage metadata requires an application I/O
policy. Acceptance performs no reads or credential acquisition.

Metadata access is separate from processing API authentication. To add scoped
headers, declare a runtime factory on an application configuration subclass:

```python
from cuiman import ClientConfig
from cuiman.api.opener import StacMetadataIO

class AppConfig(ClientConfig):
    @staticmethod
    def stac_metadata_io_factory(config):
        # Obtain this token from your application's credential provider at runtime.
        return StacMetadataIO(
            max_bytes=config.stac_metadata_max_bytes,
            timeout=config.stac_metadata_timeout,
            max_requests=config.stac_metadata_max_requests,
            headers_by_origin={
                "https://metadata.example.org": {"Authorization": "Bearer <token>"}
            },
        )
```

Use `Client(config_type=AppConfig, ...)` or AsyncClient with that configuration.
Headers apply only to explicitly listed scheme/host/port origins. Redirects
recompute headers for their destination; API credentials, response cookies, and
environment proxies are not inherited. List another origin explicitly to grant
it metadata credentials. Factories may supply fresh `sync_transport_factory` and
`async_transport_factory` transports. Runtime policy and secrets are excluded
from persisted client settings and PySTAC JSON; Cuiman metadata errors omit URLs
and underlying exception details.

Linked metadata uses its effective URI after redirects. Inline metadata prefers
an unambiguous absolute self link, then the effective result-document URI retained
by the client transport. Embedded Item references follow their ItemCollection's
containing document even if an Item advertises an unrelated self link. Native
objects receive normalized references while raw result JSON remains unchanged.
A relative reference without a known base fails instead of guessing the API URL.
Custom transports can implement `get_response_href(value)` to supply source facts;
its default returns None.

Returned objects retain an individual read-only PySTAC StacIO policy. Explicit
native navigation, such as `catalog.get_children()`, performs synchronous bounded
reads, including for objects returned by AsyncClient. Each navigated document gets
a fresh operation budget; the initial budget is not a whole-catalog crawl budget.
Initial async opening uses async HTTP I/O and off-thread local-file reads, and
propagates cancellation. This policy never changes PySTAC's global default.

The following example uses `simulate_scene` from the
[local test service](api.md#start-the-local-service). Run the Python blocks in
order from the repository root in the Pixi environment. The maintained source
is [openers.py](https://github.com/eo-tools/eozilla/blob/main/examples/guides/cuiman/openers.py).

## Prepare a small scene

This request creates two variables on a 4 × 4 grid for two dates. The generated
values are zero; the example demonstrates data access, not a scientific product.

```json
--8<-- "examples/guides/cuiman/simulate-scene-request.json"
```

`output_path` is relative to the **server's** working directory. The process
replaces existing data at that path, so choose an unused path. The example
assumes server and client run on the same machine and can access the same
filesystem. A `file://` link from a remote server is not automatically accessible
to your client. Omitting the path uses server-process memory, which a separate
client process cannot read.

## Submit once

```python
--8<-- "examples/guides/cuiman/openers.py:imports"

--8<-- "examples/guides/cuiman/openers.py:connect"

--8<-- "examples/guides/cuiman/openers.py:submit"

--8<-- "examples/guides/cuiman/openers.py:submit-call"
```

Retain the returned `job_id`. Once its status is `successful`,
`client.get_job_results(job_id)` shows a link to the dataset with media type
`application/zarr`.

## Open with a built-in opener

```python
--8<-- "examples/guides/cuiman/openers.py:builtin"

--8<-- "examples/guides/cuiman/openers.py:open-call"
```

`data_type=xr.Dataset` selects a compatible opener, `output_name` selects the
process output, and `engine="zarr"` is forwarded to xarray. The printed sizes
are `lat: 4`, `lon: 4`, and `time: 2`.

If a job has exactly one output, `output_name` can be omitted. Multiple outputs
require an explicit name, even if one is named `return_value`. A missing name or
ambiguous selection raises `JobResultOpenError` before reader dispatch. Selecting
an output whose value is `null` is valid; whether it can be opened depends on the
configured readers. `get_job_results()` retains all original names and values.

The helper waits up to 30 seconds for completion. A running job that exceeds
this deadline raises `TimeoutError`; failed or dismissed jobs raise
`JobResultStatusError`. Inspect the job before retrying. Opening an existing
job's output does not submit a new job. Always close datasets after use.

## Add a custom opener

A custom opener decides whether it can handle the requested output, then opens
it. This example specializes in local Zarr links and converts file URIs to
native paths, including on Windows. It also handles escaped spaces in paths,
which the built-in reader's current file-URI handling may not resolve. Use
paths without spaces for the built-in example, or this custom opener:

```python
--8<-- "examples/guides/cuiman/openers.py:custom"
```

The client selects the output before invoking any opener. `ctx.value` (also
available as `ctx.output_value`) is an independent copy of that selected job
output. `ctx.output_name` contains its resolved name, including when a sole
output was selected automatically. `ctx.output_link` interprets the selected
value as a Link when possible; it can be `None`. `ctx.location` holds the
effective path or URL for path readers, and `ctx.output_media_type` retains the
selected value's media type or the caller's override.

The context can also be constructed with a direct `value` and optional `location`
without producing-job information. `job_id`, `job_results`, and
`process_description` are optional source facts. Custom openers should read the
selected value/location rather than choose another output from `job_results`.
`ctx.output_description` uses the selected name to find matching process metadata;
a process schema does not independently select an output.

The acceptance check also respects the requested data type and media type.
The example imports xarray directly because it is required by this guide;
reusable plugins can implement `is_usable()` to detect optional dependencies.

Register the opener temporarily and use the same completed job:

```python
--8<-- "examples/guides/cuiman/openers.py:registration"

dataset = open_with_custom_opener(client, job_id)
try:
    print(dataset)
finally:
    dataset.close()
```

New registrations take precedence over built-ins. Registration belongs to the
client's configuration **class**, so it affects clients sharing that class.
The returned callback removes the registration, including when opening fails.
For an application's permanent extensions, prefer a `ClientConfig` subclass
with `extra_job_result_openers`; see [Customization](../customization.md).

## Close the client

```python
--8<-- "examples/guides/cuiman/openers.py:close"
```

The complete script uses `try`/`finally` for client and dataset cleanup. Run it
to submit one scene and open it with the built-in opener:

```bash
--8<-- "examples/guides/cuiman/cli.sh:python-openers"
```

The [original opener notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-openers.ipynb)
remains available as a historical example. Its assumption that no openers are
registered by default no longer applies.
