# Cuiman Configuration

The `cuiman` configuration settings may be passed in a couple of ways 
to the Python API and CLI clients. The different ways also have different 
precedence.

## Passing Configuration

In the following list of configuration methods, a setting of a subsequent 
entry overrides that of a previous one.

1. Default settings hard-coded into the `cuiman.api.ClientConfig` class.
2. Settings loaded from a given or the default configuration file passed as `config_path`.
3. Credentials stored in the operating-system keyring for that configuration
   file and API URL.
4. Settings loaded from environment variables prefixed with `EOZILLA_`.
5. Settings from another configuration object of type `cuiman.api.ClientConfig` passed as `config`.
6. Settings from keyword arguments passed directly to the client as `config_kwargs`.

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
    "auth": {
        "auth_type": "token",
        "use_bearer": true
    }
}
```

YAML:

```yaml
api_url: "https://anolis.api.org/process-api/v1"
auth:
  auth_type: token
  use_bearer: true
```

Configuration files contain only public connection and authentication metadata.
Credentials are never written to them. Files in the older format that contain
credentials are detected as legacy configuration; run `cuiman configure` to
rewrite their public values safely.

### Credential Storage

The `cuiman` CLI stores passwords, access tokens, refresh tokens, client
secrets, and API keys in the operating-system keyring. The keyring entry is
scoped to the canonical configuration-file path and the API URL, so profiles
for different services or files do not share credentials.

Environment variables and direct Python configuration remain available for
automated deployments. They take precedence over keyring values and should be
provided through the deployment platform's secret-injection mechanism.

### Environment Variables

Cuiman reads configuration from environment variables prefixed with
`EOZILLA_`. Top-level configuration fields use their uppercase field name;
nested fields use two underscores (`__`) to separate levels. For example,
`api_url` is configured with `EOZILLA_API_URL`, while the nested
`auth.auth_type` field is configured with `EOZILLA_AUTH__AUTH_TYPE`.

The following configures a service using a static bearer token:

```bash
export EOZILLA_API_URL="https://anolis.api.org/process-api/v1"
export EOZILLA_AUTH__AUTH_TYPE="token"
export EOZILLA_AUTH__ACCESS_TOKEN="ab989e20-d58609a9-8d4c"
```

The authentication type determines which other nested authentication variables
are accepted:

| Authentication type | Required environment variables | Optional environment variables |
| --- | --- | --- |
| `none` | `EOZILLA_AUTH__AUTH_TYPE=none` | |
| `basic` | `EOZILLA_AUTH__AUTH_TYPE=basic`, `EOZILLA_AUTH__USERNAME`, `EOZILLA_AUTH__PASSWORD` | |
| `token` | `EOZILLA_AUTH__AUTH_TYPE=token`, `EOZILLA_AUTH__ACCESS_TOKEN` | `EOZILLA_AUTH__USE_BEARER`, `EOZILLA_AUTH__ACCESS_TOKEN_HEADER` |
| `login` | `EOZILLA_AUTH__AUTH_TYPE=login`, `EOZILLA_AUTH__LOGIN_URL`, `EOZILLA_AUTH__USERNAME`, `EOZILLA_AUTH__PASSWORD` | `EOZILLA_AUTH__ACCESS_TOKEN`, `EOZILLA_AUTH__USE_BEARER`, `EOZILLA_AUTH__ACCESS_TOKEN_HEADER` |
| `oauth2` | `EOZILLA_AUTH__AUTH_TYPE=oauth2`, `EOZILLA_AUTH__TOKEN_URL` | `EOZILLA_AUTH__GRANT_TYPE`, `EOZILLA_AUTH__USERNAME`, `EOZILLA_AUTH__PASSWORD`, `EOZILLA_AUTH__CLIENT_ID`, `EOZILLA_AUTH__CLIENT_SECRET`, `EOZILLA_AUTH__REFRESH_TOKEN`, `EOZILLA_AUTH__ACCESS_TOKEN`, `EOZILLA_AUTH__USE_BEARER`, `EOZILLA_AUTH__ACCESS_TOKEN_HEADER` |
| `api-key` | `EOZILLA_AUTH__AUTH_TYPE=api-key`, `EOZILLA_AUTH__API_KEY` | `EOZILLA_AUTH__API_KEY_HEADER` |

For OAuth 2.0, `grant_type` defaults to `password`. The `password` grant
requires `USERNAME` and `PASSWORD`; the `client_credentials` grant requires
`CLIENT_ID` and `CLIENT_SECRET`.

Environment settings override values from the configuration file. Providing
`EOZILLA_AUTH__AUTH_TYPE` selects a complete authentication configuration, so
provide the variables required by that type as well. To override only a field
of the authentication configuration selected in the file, omit
`EOZILLA_AUTH__AUTH_TYPE`; for example, set only
`EOZILLA_AUTH__ACCESS_TOKEN` to replace a stored login token.

> Treat credential environment variables as secrets. Use the secret-injection
> mechanism of your deployment platform and do not commit them to source control.

### Configuration Object

```python
from cuiman import Client, ClientConfig

config = ClientConfig(
    api_url="https://anolis.api.org/process-api/v1",
    auth={
        "auth_type": "basic",
        "username": "polly",
        "password": "1234",
    },
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
    auth={
        "auth_type": "basic",
        "username": "polly",
        "password": "1234",
    },
)
```

### Using the CLI

Before using the CLI, configure the public service settings and then log in:

```console
$ cuiman configure
$ cuiman login
```

`configure` asks only for public connection and authentication metadata and
writes it to the configuration file. `login` asks for credentials only when
the selected authentication type requires them and stores them in the OS
keyring. `logout` removes the matching keyring entry. For authentication type
`none`, `configure` does not offer login.

When a configured authenticated service is used without available credentials,
the CLI reports `Please log in first using 'cuiman login'.` instead of showing
an implementation traceback.

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
types. The authentication type is provided by the nested `auth.auth_type`
configuration setting.

### Auth type `none`

The authentication type `none` means, the server doesn't require any 
client authentication. This is usually the case only for development 
environments.

```python
config = ClientConfig(api_url="...", auth={"auth_type": "none"})
```

### Auth type `basic`

Basic HTTP authentication is quite common for simple and older processing services. 
It requires `username` and `password`.

```python
config = ClientConfig(
    api_url="...",
    auth={
        "auth_type": "basic",
        "username": "...",
        "password": "...",
    },
)
```

### Auth type `token`

Authentication via API access tokens is widely used.
`cuiman` supports bearer tokens (as used by OAuth 2.0) as well as custom headers.

For auth type `token`, `cuiman` treats access tokens as static and does not
attempt refresh. Use auth type `oauth2` when the server supports OAuth 2.0
refresh tokens.


```python
config = ClientConfig(
    api_url="...",
    auth={
        "auth_type": "token",
        "access_token": "...",
        "use_bearer": True,  # default
    },
)
```

With custom header:

```python
config = ClientConfig(
    api_url="...",
    auth={
        "auth_type": "token",
        "access_token": "...",
        "use_bearer": False,
        "access_token_header": "X-Auth-Token",  # Default
    },
)
```

### Auth type `login`

The authorisation type `login` is for a proprietary username/password endpoint.
Cuiman posts the credentials as form fields to `login_url` and extracts an access
token from the response. It does not use the OAuth 2.0 protocol or refresh tokens.

```python
config = ClientConfig(
    api_url="...",
    auth={
        "auth_type": "login",
        "login_url": "https://identity.example.org/login",
        "username": "...",
        "password": "...",
        "access_token": "...",  # obtained by `cuiman login`
        "use_bearer": True,
    },
)
```

### Auth type `oauth2`

The `oauth2` type obtains a token from a standards-based OAuth 2.0 token
endpoint. It supports the `password` grant (the default) and the
`client_credentials` grant. If a password-grant response includes a refresh
token, Cuiman refreshes the access token once after an HTTP 401. The refreshed
token is persisted to the OS keyring when the credentials were loaded from it;
it is never written to the configuration file.

```python
config = ClientConfig(
    api_url="...",
    auth={
        "auth_type": "oauth2",
        "token_url": "https://identity.example.org/realms/example/protocol/openid-connect/token",
        "grant_type": "password",
        "username": "...",
        "password": "...",
        "client_id": "...",  # optional for password grant
        "client_secret": "...",  # optional for password grant
        "access_token": "...",  # obtained by `cuiman login`
        "refresh_token": "...",  # returned by the token endpoint when available
        "use_bearer": True,
    },
)
```

`cuiman login` supports the OAuth2 `password` grant. The
`client_credentials` grant has no interactive login step; provide its
credentials through environment variables or direct Python configuration.
OIDC authorization-code login is not included in this release.

### Auth type `api-key`

The authorisation via API keys is also very common in SaaS scenarios.
A simple API key `api_key` must be given, which is usually passed by 
a request header named `X-API-Key`:

| API Key Header | `X-API-Key: abc123` | Very common in SaaS

```python
config = ClientConfig(
    api_url="...",
    auth={
        "auth_type": "api-key",
        "api_key": "...",
        "api_key_header": "X-API-Key",  # default
    },
)
```
