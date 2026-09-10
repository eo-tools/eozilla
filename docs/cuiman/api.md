# Cuiman API Reference

The Cuiman Python API is provided by the `cuiman.api` package. Frequently 
used classes and functions are also made available directly through the 
`cuiman` package. 


## Client API

A client is created using the [`Client`](#cuiman.api.Client) class 
with a [`ClientConfig`](#cuiman.api.ClientConfig) or a dictionary of
configuration that match the attributes the configuration class.

[`Client`](#cuiman.api.Client) provides a synchronous API. If you want an 
asynchronous version, use the `AsyncClient` class instead.
It provides the same interface, but using asynchronous server calls.

Constructing a client loads configuration and credentials without logging in or
creating a process API transport. Before its first API request, the client
automatically exchanges available login/OAuth2 credentials or refresh tokens
when an access token is needed. Existing access tokens, Basic credentials, and
API keys can be used immediately.

Call `login()` explicitly to authenticate earlier or allow credential prompts
and OIDC browser login:

```python
from cuiman import Client, AsyncClient

client = Client()
client.login()  # Optional; may prompt or open the browser.
processes = client.get_processes()
client.close()

# Inside an async function:
async_client = AsyncClient()
await async_client.login()
processes = await async_client.get_processes()
await async_client.close()
```

Repeated `login()` calls reuse available authentication. Use
`login(interactive=False)` to prohibit interaction, or `login(no_browser=True)`
to print the OIDC authorization URL instead of opening it. Ordinary API calls
never prompt or open a browser. If initial authentication requires interaction,
they raise `cuiman.api.auth.LoginRequiredError` before sending a process API
request. Concurrent
first calls on one `AsyncClient` share login. Failed or cancelled initial login
can be retried, and closing an unused client does not initiate login.

Authlib refreshes tokens before known expiry and reacquires client-credentials
tokens when needed. A processing-service 401 is returned without automatic
renewal or replay. Rejected refresh propagates the library error. Use
`login(force=True)` to sign in again and allow credential prompts, or
`login(force=True, interactive=False)` for a fresh grant with supplied credentials.

`client.token` returns a copy of the live OAuth2/OIDC token. The configuration's
`oauth_token` field is only a bootstrap snapshot. Use `login(save=True)` to require
durable storage in the profile's OS-keyring entry and enable subsequent refresh
updates to that profile. Optional refresh-save failures
warn while keeping the live token usable. `logout()` revokes OIDC tokens when
supported, removes local credentials, and closes the client; await it for
`AsyncClient`. A closed client cannot be reused.

The launched app borrows this same client's requester. See
[Authentication](authentication.md) for storage, error behavior, and event-loop
ownership requirements.

Methods of the [`Client`](#cuiman.api.Client) and `AsyncClient` 
may raise a [`ClientError`](#cuiman.api.ClientError) if a server call fails. 

::: cuiman.api.Client

::: cuiman.api.ClientError


## Configuration API

::: cuiman.api.ClientConfig


## Auth Configuration API

!!! warning "Warning"

    The Client Auth Configuration API is not stable and may change without 
    notice. Do not yet rely on it.

### OpenID Connect

`OidcAuthConfig` describes a public OIDC client: its issuer URL, client ID,
and optional scopes. `openid` is always included. Use `client.login()` or
`cuiman login` for the
interactive Authorization Code with PKCE flow; the resulting access and refresh
tokens are secrets and belong in the operating-system keyring, not a
configuration file. Use the client lifecycle for discovery, authorization,
refresh, and logout; one-shot protocol helpers are no longer public APIs.

::: cuiman.api.auth


## Job Result Opener API

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.opener.JobResultOpenContext

::: cuiman.api.opener.JobResultOpenerRegistry


## CLI API

::: cuiman.cli.new_cli
