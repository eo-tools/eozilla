# Job result openers

`client.get_job_results(job_id)` retrieves result values and references.
`client.open_job_result(job_id)` waits for completion and opens a selected
output using a registered opener. Cuiman includes xarray, pandas, and GeoPandas
openers; each requires its corresponding optional library. Custom openers
extend or specialize this behavior.

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

`ctx.output_link` resolves the requested output name; it can be `None`.
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
