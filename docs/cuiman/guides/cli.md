# Command-line guide

Use `cuiman` to discover processes, submit jobs, and retrieve their results.
The commands below are maintained in
[cli.sh](https://github.com/eo-tools/eozilla/blob/main/examples/guides/cuiman/cli.sh).
Copy individual recipes into Bash or PowerShell. Running the entire file as a
script exits immediately without executing the recipes.

## Start and configure

In a development checkout, run `pixi install`, then start the test service in a
separate terminal:

```bash
--8<-- "examples/guides/cuiman/cli.sh:server"
```

In a second terminal, run `pixi shell` from the repository root and configure
Cuiman for this unauthenticated local service:

```bash
--8<-- "examples/guides/cuiman/cli.sh:configure"
```

This updates the saved Cuiman profile. For a remote deployment, use its URL and
authentication settings, then `cuiman login` when interactive sign-in is needed.
See [Configuration](../configuration.md) and [Authentication](../authentication.md).

## Inspect a process

```bash
--8<-- "examples/guides/cuiman/cli.sh:inspect"
```

The local service provides `primes_between`, with integer inputs `min_val` and
`max_val`. Inspect the actual process description when using another service.
Add `--help` after any command for its arguments and options.

## Prepare and validate inputs

Print a request template:

```bash
--8<-- "examples/guides/cuiman/cli.sh:template"
```

To use a file, copy the JSON into a UTF-8 file named `request.json`, edit its
inputs, then pass `--request request.json` to validation or submission. Explicit
UTF-8 saving also avoids Windows PowerShell 5.1's UTF-16 redirection default.
Generated defaults are only a starting point.

For this small request, supply inputs directly:

```bash
--8<-- "examples/guides/cuiman/cli.sh:validate"
```

Validation checks the request structure locally. It does not contact the service
or validate all process-specific constraints.

## Submit a job

```bash
--8<-- "examples/guides/cuiman/cli.sh:submit"
```

Save the `jobID` printed by the server. Replace `YOUR_JOB_ID` below with that
value. Submission starts a new job each time; it does not wait for completion.

## Monitor and retrieve results

```bash
--8<-- "examples/guides/cuiman/cli.sh:jobs"
```

Repeat `get-job` while the status is `accepted` or `running`. Once it is
`successful`, retrieve the results:

```bash
--8<-- "examples/guides/cuiman/cli.sh:results"
```

The prime-number result contains the primes from 11 through 79. For an example
that deliberately fails, submit:

```bash
--8<-- "examples/guides/cuiman/cli.sh:failure"
```

Inspect this new job using its own returned ID. Its failed status and message
explain why successful results are unavailable.

## Use a JSON request for a dataset

The [result opener guide](openers.md) provides a small scene request. It writes
`guide-scene.zarr` relative to the server's working directory, replacing any
existing dataset at that path. Choose an unused `output_path` before submitting.
Validate and then submit it:

```bash
--8<-- "examples/guides/cuiman/cli.sh:scene-validate"

--8<-- "examples/guides/cuiman/cli.sh:scene-submit"
```

Retain this job's returned ID. Its result links to the dataset; use the
[Python opener example](openers.md#open-with-a-built-in-opener) to read it.

## Cancel or delete a selected job

This cancels a running job or deletes a finished job:

```bash
--8<-- "examples/guides/cuiman/cli.sh:dismiss"
```

## Open the App

```bash
--8<-- "examples/guides/cuiman/cli.sh:app"
```

Keep the terminal running; press Ctrl+C to stop the App server. See the
[App guide](app.md) for the visual workflow and the [CLI Reference](../cli.md)
for the complete command list.

The [original CLI notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-cli.ipynb)
remains available as a historical example; use the commands above with the
current client.
