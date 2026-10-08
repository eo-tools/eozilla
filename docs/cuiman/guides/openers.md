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
import pandas as pd
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
    asset = items[0].assets["report"]
    report = client.open_job_result(asset, data_type=pd.DataFrame)
    print(report["mean_ndvi"].tolist())  # [1.5]
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
links remain available without automatic pagination. Transformation composition
is introduced in a subsequent implementation step.

### Open exactly one Asset

Both Client and AsyncClient accept `pystac.Asset` as the first `job_id_or_asset` argument;
AsyncClient uses `await client.open_job_result(asset, ...)`. Select an Asset from
native metadata, or construct an independent Asset with an absolute href. The
receiving client uses its own registered readers and configuration, including for
Assets obtained through another client. No processing API calls, metadata
rediscovery, sibling selection, or transformations occur during Asset opening.
Strings always identify jobs, including strings that look like URLs. Other
targets, including native Items and Catalogs, raise TypeError.

Asset calls accept `data_type`, `media_type`, and reader options such as
`engine="zarr"`. Omit `output_name`, `poll_interval`, and `timeout`: explicitly
supplying any of them raises TypeError before resolution or dispatch, including
None and the usual job defaults. Producer reader hints and scoped Asset-access
configuration are introduced in the next implementation step; currently reader
options come from the caller.

The exact Asset remains the selected context value. Its own media type takes
precedence over its filename suffix; neither the owner's GeoJSON type nor sibling
metadata determines its format. A caller override leaves the Asset unchanged.
Media-type parameters and signed URL queries remain intact. Relative hrefs use
the owner's absolute self-document location; missing or relative owner bases
fail clearly. Native Windows paths and file URIs, including escaped spaces, work
with built-in path readers. Suffix matching ignores URL queries and fragments.
The selected data reader controls payload I/O.

The testing processes also provide `assets["data"]` as Zarr. Read that Asset with
`data_type=xr.Dataset, engine="zarr"` and close the returned dataset after use.
Reading Zarr over HTTP additionally requires the reader's HTTP dependencies
(`fsspec[http]`, including aiohttp), which the current Pixi environment does not
include. The CSV example above runs with the existing development dependencies.

### Standard PySTAC metadata I/O

Metadata reads use `pystac.StacIO.default()` and return native PySTAC objects.
Cuiman adds no metadata response-size limit, per-fetch timeout, request budget,
or transport cache. The proposed 2 MiB, 10-second, and 16-request bounds are an
optional future extension, not current behavior. HTTP and local metadata files,
including Windows paths and file URIs with escaped spaces, are supported.
Acceptance performs no reads or credential acquisition.

Applications may set `ClientConfig.stac_io_factory` to a callable taking the
receiving configuration and returning a native `pystac.StacIO`. The factory runs
once per opening and is excluded from saved settings. Returned objects retain
that I/O for ordinary navigation. Applications own any custom headers, storage
support, timeout, or redirect policy; Cuiman does not copy processing API
credentials into metadata requests or change PySTAC's global default.

Linked metadata uses its supplied document URL or an unambiguous absolute self
link. PySTAC's default I/O does not expose the final response URL after redirects.
If relative references depend on a changed redirect location, provide an absolute
self link or an appropriate application I/O implementation. Inline metadata prefers
an unambiguous absolute self link, then the effective result-document URI retained
by the client transport. Embedded Item references follow their ItemCollection's
containing document even if an Item advertises an unrelated self link. Native
objects receive normalized references while raw result JSON remains unchanged.
A relative reference without a known base fails instead of guessing the API URL.
Custom transports can implement `get_response_href(value)` to supply source facts;
its default returns None.

Explicit native navigation, such as `catalog.get_children()`, uses normal
synchronous PySTAC I/O, including for objects returned by AsyncClient. Initial
metadata reads run in a worker thread to keep the async event loop responsive.
Cancellation of the awaiting task propagates, but an already running synchronous
read may continue until PySTAC completes it. Cuiman's initial-opening errors omit
URLs and underlying exception details; later native navigation uses PySTAC's own
error behavior.

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
native paths, including escaped spaces on Windows:

```python
--8<-- "examples/guides/cuiman/openers.py:custom"
```

The client selects the output before invoking any opener. `ctx.value` (also
available as `ctx.output_value`) is an independent copy of that selected job
output. For an Asset call, `ctx.value` is the exact
supplied native Asset, with optional job facts absent. `ctx.output_name` contains
its resolved name for job calls, including when a sole
output was selected automatically. `ctx.output_link` interprets the selected
value as a Link when possible; it can be `None`. `ctx.location` holds the
effective path or URL for path readers, and `ctx.output_media_type` retains the
selected value's media type or the caller's override.

The context carries shared opening facts; opener-specific runtime state belongs
to the opener instance. STAC opening obtains a native I/O instance for every opening,
including when an opener or context is reused. Returned native objects retain
their own navigation policy without storing STAC-specific state on the context.

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
