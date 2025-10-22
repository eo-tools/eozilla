# Client API Reference

The [`Client`](#cuiman.Client) class provides a synchronous API.
If you want an asynchronous version, use the `AsyncClient` class instead.
It provides the same interface, but using asynchronous server calls.

Both clients return their configuration as a 
[`ClientConfig`](#cuiman.ClientConfig) object.

Methods of the [`Client`](#cuiman.Client) and `AsyncClient` 
may raise a [`ClientError`](#cuiman.ClientError) if a server call fails. 

::: cuiman.Client

::: cuiman.ClientConfig

::: cuiman.ClientError
