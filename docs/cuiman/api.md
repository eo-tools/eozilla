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

Methods of the [`Client`](#cuiman.api.Client) and `AsyncClient` 
may raise a [`ClientError`](#cuiman.api.ClientError) if a server call fails. 

## App Launch

`Client.show_app()` starts the Cuiman app server and opens the Eozilla App.
The initial browser URL contains only a short-lived, single-use `launch` code.
The app exchanges it for an HttpOnly same-origin session cookie, then replaces
it with the non-sensitive `cuiman=1` reload marker. It derives its service
proxy and RemoteState WebSocket URLs from the browser-visible app URL, so the
same flow works through a Jupyter Server Proxy path prefix without exposing
the configured service URL or credentials to the browser.

::: cuiman.api.Client

::: cuiman.api.ClientError


## Configuration API

::: cuiman.api.ClientConfig


## Auth Configuration API

!!! warning "Warning"

    The Client Auth Configuration API is not stable and may change without 
    notice. Do not yet rely on it.

::: cuiman.api.auth


## Job Result Opener API

::: cuiman.api.opener.JobResultOpener

::: cuiman.api.opener.JobResultOpenContext

::: cuiman.api.opener.JobResultOpenerRegistry


## CLI API

::: cuiman.cli.new_cli
