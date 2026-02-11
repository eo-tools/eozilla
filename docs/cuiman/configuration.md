# Cuiman Configuration

The `cuiman` configuration settings may be passed in a couple of ways 
to the Python API and CLI clients. The different ways also have different 
precedence.

## Passing Configuration

In the following list of configuration methods, a setting of a subsequent 
entry overrides that of a previous one.

1. Default settings hard-coded into the `cuiman.ClientConfig` class.
2. Settings loaded from a given or the default configuration file passed as `config_path`.
3. Settings loaded from environment variables prefixed with `EOZILLA_`.
4. Settings from another configuration object of type `cuiman.ClientConfig` passes as `config`.
5. Settings from keyword arguments passed directly to the client passed as `config_kwargs`.

This list is implemented in the class method `create()` of the 
`cuiman.api.ClientConfig` class. 

Note that applications using `cuiman` under the hood may customize the 
configuration, see [Cuiman Customization](./customization.md). 

### Configuration Files

```python
from cuiman import Client

client = Client(config_path="./my-config.json")
```

Configuration files have either YAML or JSON format.

JSON:

```json
{
    "api_url": "https://anolis.api.org/process-api/v1", 
    "auth_type": "token",
    "token": "ab989e20-d58609a9-8d4c",
    "use_bearer": true
}
```

YAML:

```yaml
api_url: "https://anolis.api.org/process-api/v1" 
auth_type: token
token: ab989e20-d58609a9-8d4c
use_bearer: true
```

### Environment Variables

All configuration parameters can be passed as environment variables
using the uppercase parameter name prefixed by `EOZILLA_`.

With

```bash
export EOZILLA_USERNAME="polly"
export EOZILLA_PASSWORD= "1234"
```

set, you no longer need to pass `username` and `password`:

```python
from cuiman import Client

client = Client(
    api_url="https://anolis.api.org/process-api/v1", 
    auth_type="basic"
)
```

### Configuration Object

```python
from cuiman import Client, ClientConfig

config = ClientConfig(
    api_url="https://anolis.api.org/process-api/v1", 
    auth_type="basic",
    username="polly",
    password="1234",
)

client = Client(config=config)
```

### Keyword Arguments

Pass configuration settings as keyword arguments 
directly to the client constructor:

```python
from cuiman import Client

client = Client(
    api_url="https://anolis.api.org/process-api/v1", 
    auth_type="basic",
    username="polly",
    password="1234",
)
```

### Using the CLI

Before using the CLI, you should configure it using the `cuiman configure`
command. 

You can override settings anytime from environment variables or by using   
the `--config/-c <file>` option supported by most CLI commands.

## Basic Settings

The most important configuration setting is `api_url` which provides the 
base URL to the OGC API - Processes.

By default, `cuiman` assumes the service the API URL is pointing to 
does not perform any authorisation on the incoming requests - which 
is rarely the case. Therefore, the client need to be configured with 
respect to some service-specific authorisation method.

## Authentication Settings

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

