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

`get_job_results(job_id)` waits for successful completion and returns `JobResults`
containing inline values and output links. It does not open outputs or download
linked data. Pass `wait=False` to request results immediately, preserving the
behavior of earlier versions.

```python
results = client.get_job_results(job_id)
results = client.get_job_results(job_id, timeout=60, poll_interval=0.5)
results = client.get_job_results(job_id, wait=False)
```

Both clients poll accepted and running jobs, using a 30-minute timeout and a
0.5-second polling interval by default. Failed or dismissed jobs raise
`JobResultStatusError`; expiration raises `TimeoutError` and leaves the remote
job running. `timeout` controls the completion wait rather than an HTTP request
timeout. With `wait=False`, `timeout`, `poll_interval`, and `monitor` are ignored.

An optional `JobMonitor` receives the initial status and each subsequent update,
including progress. Calling its `cancel()` method explicitly requests dismissal
of a pending job. Its handler can be synchronous or asynchronous:

```python
from cuiman import JobMonitor

monitor = JobMonitor(lambda job: print(job.status, job.progress))
results = client.get_job_results(job_id, monitor=monitor)
# With AsyncClient inside an async function:
results = await async_client.get_job_results(job_id, monitor=monitor)
```

::: cuiman.api.Client

::: cuiman.api.AsyncClient

::: cuiman.api.ClientError

::: cuiman.api.jobs.JobMonitor

::: cuiman.api.jobs.JobOptions

::: cuiman.api.opener.JobResultStatusError


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

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.opener.JobResultOpenContext

::: cuiman.api.opener.JobResultOpenerRegistry

## App API

::: cuiman.app.App


## CLI API

::: cuiman.cli.new_cli
