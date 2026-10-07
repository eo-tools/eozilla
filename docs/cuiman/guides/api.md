# Python API guide

Discover processes, submit work, and inspect results using `cuiman.Client`.
For installation and client concepts, start with [Getting Started](../getting-started.md).

## Start the local service

The examples use Eozilla's local test service, which needs no credentials.
From a development checkout with `pixi install` completed, keep this command
running in a separate terminal:

```bash
--8<-- "examples/guides/cuiman/cli.sh:server"
```

In another terminal, run `pixi shell` from the repository root and start Python
or Jupyter. Run the following blocks in order in the same session. Each helper
definition is followed by its call; keep the returned client and job ID for
subsequent steps. The complete source is
[api.py](https://github.com/eo-tools/eozilla/blob/main/examples/guides/cuiman/api.py).

## Create a client

```python
--8<-- "examples/guides/cuiman/api.py:imports"

--8<-- "examples/guides/cuiman/api.py:create-client"

--8<-- "examples/guides/cuiman/api.py:connect-call"
```

The explicit URL and `auth_type="none"` select the local service. To connect to
your own deployment, use its [configuration](../configuration.md) instead.
Constructing a client does not log in. Requests authenticate using available
credentials; call `client.login()` first when interactive sign-in is needed.
See [Authentication](../authentication.md).

## Discover processes

```python
--8<-- "examples/guides/cuiman/api.py:inspect"

--8<-- "examples/guides/cuiman/api.py:inspect-call"
```

The local `primes_between` process returns prime numbers between two input
values. Other services expose different process IDs, inputs, and outputs;
inspect their descriptions before preparing a request. You can also inspect
the service with `client.get_capabilities()` and `client.get_conformance()`.

## Submit once

```python
--8<-- "examples/guides/cuiman/api.py:submit"

--8<-- "examples/guides/cuiman/api.py:submit-call"
```

Submission starts an asynchronous job and returns its information. The returned
`job_id` identifies this execution; running the submission again creates a new job.
The request is a `ProcessRequest`; a request dictionary is also accepted by
`client.execute_process()`.

## Monitor and retrieve results

```python
--8<-- "examples/guides/cuiman/api.py:results"

--8<-- "examples/guides/cuiman/api.py:results-call"
```

If the job is still accepted or running, repeat only
`inspect_results(client, job_id)` later. A successful result contains the prime
numbers from 11 through 79. Failed or dismissed jobs have no successful result;
inspect the job's status and message. `client.get_jobs()` lists jobs.

To try failure handling deliberately, define and call:

```python
--8<-- "examples/guides/cuiman/api.py:failure"

failed_job_id = submit_failure_example(client)
```

After roughly two seconds, use `inspect_results(client, failed_job_id)` to see
the failure. To cancel a running job or delete a finished one, call
`client.dismiss_job(job_id)` with the specific job you intend to dismiss.

For file or dataset outputs, [Result openers](openers.md) explains the
difference between retrieving result references and opening their data.

## Close the client

When finished with this session:

```python
--8<-- "examples/guides/cuiman/api.py:close"
```

In a script, put the workflow in `try` and cleanup in `finally`, as shown by
`example_session()` in the source file. Run that complete example with:

```bash
--8<-- "examples/guides/cuiman/cli.sh:python-api"
```

It submits one job, checks once, and closes the client. If results are not ready,
retain its printed job ID and inspect it with a new client or the
[CLI](cli.md#monitor-and-retrieve-results).

See [Getting Started](../getting-started.md#use-an-asynchronous-client) for
`AsyncClient`, and the [API Reference](../api.md) for all methods.
The [original API notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-api.ipynb)
and [Airflow notebook](https://github.com/eo-tools/eozilla/blob/main/notebooks/cuiman-api-airflow.ipynb)
remain available as independent historical examples; their saved outputs and
setup instructions may differ from the current client.
