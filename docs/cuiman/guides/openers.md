# Job result openers

`client.get_job_results(job_id)` retrieves result values and references.
`client.open_job_result(job_id)` waits for completion and opens a selected
original output using a registered opener. `client.open_job_result(resource)`
reads exactly an explicitly selected `JobResultResource`, using the receiving
client's configuration, without job polling or another discovery step.
Both forms use the same reader contract. Cuiman includes Pillow, xarray, pandas, and
GeoPandas openers; each requires its corresponding optional library. The Pillow
image opener takes precedence over the dataset openers for supported images,
including PNG and JPEG, and returns a `PIL.Image.Image`. Custom openers extend
or specialize this behavior.

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
The fresh temporary profile path avoids loading a personal client profile; this
walkthrough never saves one.

## Open with a built-in opener

```python
--8<-- "examples/guides/cuiman/openers.py:builtin"

--8<-- "examples/guides/cuiman/openers.py:open-call"
```

`data_type=xr.Dataset` selects a compatible opener and `output_name` selects the
original process output. The xarray opener derives `engine="zarr"` from the
selected resource's `application/zarr` media type. Caller options can override
that default. The printed sizes
are `lat: 4`, `lon: 4`, and `time: 2`.

The helper waits up to 30 seconds for completion. A running job that exceeds
this deadline raises `TimeoutError`; failed or dismissed jobs raise
`JobResultStatusError`. Inspect the job before retrying. Opening an existing
job's output does not submit a new job. Always close datasets after use.

## Open an explicit resource

A resource is a portable description of one target: its selected link or inline
value, format, ownership, and optional reader hints. It contains no live client
or resolved storage credentials. For this process's ordinary Zarr Link, we can
construct a description directly after the job has completed:

```python
--8<-- "examples/guides/cuiman/openers.py:resource"

--8<-- "examples/guides/cuiman/openers.py:resource-call"
```

This opens the same dataset with `chunks=None` forwarded to xarray. The original
resource stays unchanged. For STAC or other compound outputs, a resolver creates
the descriptions and their stable selectors; the [resolver guide](resolvers.md)
demonstrates selecting a CSV Asset and a configured folder descendant.

Strings always identify jobs, even if they look like URLs. Use a resource to open
an explicit URL. When passing a resource, omit `output_name`, `poll_interval`, and
`timeout`: they are job-only arguments and explicitly supplying them raises
`TypeError`, including `None` or their usual defaults. Opening an original STAC
output by job ID does not automatically select an Asset inside it.

## Reader settings and storage access

The effective options are assembled separately for each candidate, in this order:

1. Reader defaults derived from the selected resource's metadata.
2. Validated Link `x-options` and opener-scoped `resource.open_hints`.
3. Client configuration's reader overrides.
4. Explicit options passed to `open_job_result()`.

Later settings take priority. Only mapping options declared mergeable by the
opener merge by key; lists and scalars replace, and `None` clears an inherited
setting. For xarray, `storage_options` is an alias for
`backend_kwargs.storage_options`. `media_type=` overrides format interpretation
without changing the advertised type stored on the resource.

Acceptance checks descriptions and the requested Python return type. It does not
read data or acquire storage credentials. A configured `ResourceAccessProvider`
supplies locally authorized access only when the chosen reader reads the target.
Processing-service login credentials are not automatically forwarded to storage.
See [Opening extensions](../customization.md#opening-extensions) for hint schemas,
option inspection, and implementing an access provider.

## Add a custom opener

A custom opener decides whether it can handle the requested output, then opens
it. This example specializes in local Zarr links and converts file URIs to
native paths, including on Windows. It also handles escaped spaces in paths,
as do the built-in path readers:

```python
--8<-- "examples/guides/cuiman/openers.py:custom"
```

`resource.link` is the selected output or Asset's link; it can be `None`.
The acceptance check also respects the requested data type and media type.
The example imports xarray directly because it is required by this guide;
reusable plugins can implement `is_usable()` to detect optional dependencies.

The client's resource overload, `client.open_job_result(resource)`, uses the same
opener methods and opens exactly the supplied resource without polling or
repeating discovery. `context` supplies this client's requested type, media type
override, and reader settings. Call `context.reader_options(resource)` only when
reading; acceptance must not acquire storage credentials. Original job/output
information remains in `resource.provenance`.

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
to submit one scene and open it by job ID and by explicit resource:

```bash
--8<-- "examples/guides/cuiman/cli.sh:python-openers"
```

The current [job result resources notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-job-result-resources.ipynb)
demonstrates STAC discovery, selection, composition, and resource opening with
the testing service. The [original opener notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-openers.ipynb)
remains available as a historical example. Its assumption that no openers are
registered by default no longer applies.
