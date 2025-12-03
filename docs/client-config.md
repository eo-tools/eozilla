# Client Configuration

## Server Configuration

TODO

## Authentication Configuration

The `cuiman` package allows for a limited set of client authentication
types. The authentication type is provided by the `auth_type` configuration
setting.

### Auth type `none`

The authentication type `none` means, the server doesn't require any 
client authentication. This is usually the case only for development 
environments.

```python
config = ClientConfig(api_url="...", auth_type="none")
```

### Auth type `basic`

Basic HTTP authentication is quite common for simple and older processing services. 
It requires `username` and `password`.

```python
config = ClientConfig(
    api_url="...", 
    auth_type="basic", 
    username="...", 
    password="...",
)
```

### Auth type `token`

Authentication via API access tokens is widely used.
`cuiman` supports bearer tokens (as used by OAuth 2.0) as well as custom headers.

Note that `cuiman` currently only supports _permanent_ access tokens.
We have not yet implemented support for _volatile_ access tokens, as
used in the _OAuth 2.0 Refresh Token Flow_. 


```python
config = ClientConfig(
    api_url="...", 
    auth_type="token", 
    use_bearer=True,
)
```

With custom header:

```python
config = ClientConfig(
    api_url="...", 
    auth_type="token", 
    use_bearer=False, 
    token_header="X-Auth-Token",  # Default
)
```

### Auth type `login`

The authorisation type `login` represents a standard enterprise scenario, where 
an access token is fetched from a server given user credentials.
This is the case for, e.g., the _OAuth 2.0 Client Credentials_.

Note that `cuiman` currently only supports _permanent_ access tokens.
We have not yet implemented support for _short-lived_ access tokens that need to be
refreshed once in a while as is the case for the _OAuth 2.0 Refresh Token Flow_. 

The authorisation type `login` requires configuration of a authorisation
URL that is used to obtain the access token:

```python
config = ClientConfig(
    api_url="...", 
    auth_type="login",
    auth_url="...",
    username="...", 
    password="...",
    # See auth_type "token" above
    use_bearer=True,
)
```

### Auth type `api-key`

The authorisation via API keys is also very common in SaaS scenarios.
A simple API key `api_key` must be given, which is usually passed by 
a request header named `X-API-Key`:

| API Key Header | `X-API-Key: abc123` | Very common in SaaS

```python
config = ClientConfig(
    api_url="...", 
    auth_type="api-key",
    api_key="...",
    api_key_header="X-API-Key",  # default
)
```

