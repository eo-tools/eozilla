# Cuiman API Reference

The Cuiman Python API is provided by the `cuiman.api` package. Frequently 
used classes and functions are also made available directly through the 
`cuiman` package. 


## Client API

`Client` provides the synchronous processing API; `AsyncClient` provides the
same interface with asynchronous server calls. Server calls may raise
`ClientError` if they fail.

With the default HTTPX2 transport, additional method `**kwargs` are forwarded to
the underlying HTTPX2 request method and follow its semantics. This includes
HTTPX2 authentication options, which are distinct from Cuiman's constructor
configuration. Configure authentication on the client for normal use.

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

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.opener.JobResultOpenContext

::: cuiman.api.opener.JobResultOpenerRegistry

## App API

::: cuiman.app.App


## CLI API

::: cuiman.cli.new_cli
