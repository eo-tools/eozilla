# Getting Started

Cuiman is a client for processing services that implement OGC API - Processes.
It lets you discover available processes, run them with your own inputs, and
retrieve their results through a Python API or command-line interface (CLI).

## Basic concepts

- A **client** connects to a processing service. Its configuration specifies
  the service URL and any authentication settings.
- A **process** is an operation offered by that service. Its description tells
  you which inputs it accepts and which outputs it produces.
- A **job** represents a process execution. You can inspect its status and
  retrieve its results when it finishes.

The usual workflow is to list the service's processes with `get_processes()`,
inspect one with `get_process(process_id)`, and run it with `execute_process()`.
Use `get_job(job_id)` to check a job's status and `get_job_results(job_id)` to
retrieve its results. The [Python API usage notebook](../notebooks/cuiman-api.ipynb)
walks through this workflow.

## Create a Python client

The Python API is provided by the `cuiman.api` package. Frequently used classes
and functions are also available directly from `cuiman`.

Create a `Client` with your service's URL. The example below assumes a service
that does not require authentication; replace the placeholder URL with yours.

```python
from cuiman import Client

client = Client(api_url="https://your-service.example.com", auth={"auth_type": "none"})
try:
    processes = client.get_processes()
    print(processes)
finally:
    client.close()
```

`Client` provides a synchronous API: each call waits for its response. You can
pass settings directly as keyword arguments, as above, or supply a
`ClientConfig` object through `config=`. Settings can also come from a
configuration file or environment variables. See [Configuration](configuration.md)
for the available settings and their precedence.

Constructing a client loads configuration and credentials without logging in.
Before its first API request, the client automatically authenticates using
available credentials when needed. Ordinary API calls never prompt or open a
browser. If your service requires credential prompts or OIDC browser login,
configure its authentication settings and call `client.login()` before making
requests. See [Authentication](authentication.md) for login and credential storage.

Always close the client when you are finished to release its connections.
A closed client cannot be reused. Server calls may raise `ClientError` if they
fail.

## Use an asynchronous client

`AsyncClient` provides the same processing interface with asynchronous server
calls. Inside an async function, await its requests and close it with `await`:

```python
from cuiman import AsyncClient


async def list_processes():
    client = AsyncClient(
        api_url="https://your-service.example.com", auth={"auth_type": "none"}
    )
    try:
        return await client.get_processes()
    finally:
        await client.close()
```

When explicit login is needed, use `await client.login()` before the requests.

## Use the command line

Run `cuiman configure` to set up the service URL and authentication. Run
`cuiman login` if you need to sign in interactively or save credentials. The
[CLI usage notebook](../notebooks/cuiman-cli.ipynb) demonstrates processing
commands, and the [CLI Reference](cli.md) lists their options.

For Python classes, method signatures, and parameters, see the
[API Reference](api.md).
