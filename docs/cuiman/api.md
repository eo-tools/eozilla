# # Cuiman API Reference

The Cuiman Python API is provided by the `cuiman` package.

The [`Client`](#cuiman.Client) class provides a synchronous API.
If you want an asynchronous version, use the `AsyncClient` class instead.
It provides the same interface, but using asynchronous server calls.

Both clients return their configuration as a 
[`ClientConfig`](#cuiman.ClientConfig) object.

Methods of the [`Client`](#cuiman.Client) and `AsyncClient` 
may raise a [`ClientError`](#cuiman.ClientError) if a server call fails. 

## Authentication notes

When `auth_type="login"`, the client performs a login call to obtain an access
token. If the auth server returns a `refresh_token`, it is stored in the config
and used to refresh the access token on HTTP 401 (with a single retry). For
`auth_type="token"`, the access token is treated as static and no refresh is
attempted.

::: cuiman.Client

::: cuiman.ClientConfig

::: cuiman.ClientError
