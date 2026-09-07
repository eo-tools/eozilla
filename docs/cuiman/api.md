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
never prompt or open a browser: they raise `cuiman.api.auth.LoginRequiredError`
before sending a process API request if interaction is required. Concurrent
first calls on one `AsyncClient` share login. Failed or cancelled initial login
can be retried, and closing an unused client does not initiate login.

OAuth2/OIDC token refresh after HTTP 401 continues to work automatically. Login
and refreshed credentials are persisted when the client has a file-backed
keyring credential source; direct Python/environment credentials remain runtime
overrides. The `auth_headers` property itself does not perform network I/O.

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
configuration file. The public helpers below expose provider discovery, PKCE,
code exchange, token refresh, revocation, and the loopback callback server for
applications that need to implement the same flow themselves.

The proprietary-endpoint helpers `login()` and `login_async()` now return
`TokenResult` rather than a token string. Use `result.access_token` when only
the access token is needed. The former `login_for_tokens()` and
`login_async_for_tokens()` names have been removed.

::: cuiman.api.auth


## Job Result Opener API

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.opener.JobResultOpenContext

::: cuiman.api.opener.JobResultOpenerRegistry


## CLI API

::: cuiman.cli.new_cli
