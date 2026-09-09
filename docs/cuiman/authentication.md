# Authentication lifecycle

Cuiman's Python clients use persistent Authlib HTTPX2 clients for OAuth2
`client_credentials`. Password grants, OIDC, the CLI, and the launched-app proxy
currently retain the shared session helpers while Authlib integration proceeds
in separately reviewed steps. Ordinary API calls never prompt or open a browser.

## Client credentials in Python clients

For `Client` and `AsyncClient`, Authlib owns the live token and sends authenticated
API requests through the same HTTP client used to obtain it. It tracks expiry and
automatically obtains a new client-credentials token before an expired token is
used. Provider-supplied refresh tokens are ignored for this grant. Requests still
retry at most once after HTTP 401 by obtaining another client-credentials token.
Without expiry metadata, an injected access token can be used until rejected.

`client.login()` prepares this client without making an API request;
`client.login(force=True)` obtains a fresh token. Use `await` for asynchronous
login, API calls, and `close()`. Close the client even if only login was called,
or login failed. Generated `Client`/`AsyncClient` classes delegate runtime
initialization and closing to their handwritten mixins; their source is
`tools/gen_client.py`.

Read `client.token` for an independent snapshot of the live token, including
`expires_at`. It returns `None` before initialization and never initiates login.
The token is a credential: do not save it in notebook output or logs. For this
grant, `client.config.auth.access_token` and `oauth_token` are **initial values**,
not a live token interface. Use `client.token` instead of config token/header
properties after login. Other authentication mechanisms have not yet changed
their token interface.

Custom token headers remain supported. Explicit per-request `auth` or an override
of the configured token header bypasses Authlib signing and the 401 renewal
callback for that request.

When a persistence hook is configured, Cuiman saves a complete token snapshot,
including its absolute expiry, under the string-valued keyring field
`oauth_token`. Existing access-token-only records still load. An explicitly
supplied `access_token` discards the snapshot's expiry and other metadata.
Public configuration files and notebook configuration representations omit all
credentials. Python/environment credentials retain their runtime-only precedence;
they do not automatically enable keyring storage. `cuiman login` continues to
reject the client-credentials grant: supply client credentials through Python
or environment variables.

Authlib installs new tokens before persistence. If the configured store raises
`SecretStoreError`, Cuiman emits `CredentialStorageWarning` and the API request
can continue using the new token. Once storage recovers, `client.login()` can
retry saving the current token without obtaining another one. Unexpected
persistence errors propagate. Stopping the process before a successful save
may require authentication again. The current keyring callback is synchronous,
including in async clients, so a slow keyring can block the event loop during a
save; worker-backed persistence and cancellation handling remain a later step.

Authlib coordinates automatic async expiry renewal. This step does not add
coordination across explicit login, 401 recovery, threads, or separate clients.
The launched-app proxy still uses its legacy authentication path and does not
borrow the Python client's Authlib session yet.

## Responsibilities

The table below describes the remaining session-based authentication paths.
For Python client credentials, `auth.client_credentials` constructs Authlib
clients and adapts provider responses and persistence; token lifecycle decisions
remain with Authlib.

| Component | Responsibility |
| --- | --- |
| `auth.config` | Authentication settings, credentials, header rendering, and the optional persistence hook. Its renewal methods delegate to `auth.session`. |
| `auth.session` | Decide whether credentials are sufficient, select token acquisition or renewal, and commit credentials through one shared path. |
| `auth.tokens.TokenResult` | Protocol-independent result containing access and optional refresh tokens. It remains exported from `cuiman.api.auth`. |
| `auth.login`, `auth.oauth2`, `auth.oidc`, and async counterparts | Execute protocol requests and return token results. They do not update live configuration or persist credentials. |
| `auth.interactive` | Explicit credential prompts and browser login, including callback handling and cancellation. Returns a candidate configuration for the session to commit. |
| `auth.secret_store` | OS-keyring storage, including Windows entry-size handling. |
| Client mixins | Explicit versus automatic login, coordination of asynchronous initial login, and lazy transport creation. |
| HTTP transport and app proxy | Send requests and retry one 401 response using the session's optional renewal callback. They do not select grants or persist tokens. |

The public configuration methods that create renewal callbacks remain available
as delegates. Callers can also use the session callback factories directly.
No provider registry or additional backend abstraction is needed at this stage.

## Token updates

The remaining session-based paths use these protocol selection and commit rules:

- OAuth2 password grants use an existing refresh token when available;
  otherwise they obtain tokens using the supplied credentials.
- If a refresh request returns HTTP 400 with OAuth2 `invalid_grant`, password
  grants can recover with one fresh login using available username/password
  credentials. OIDC and password grants without those credentials raise
  `LoginRequiredError` with instructions for explicit fresh login. Other
  errors propagate without recovery, and API calls never start interaction.
- Client-credentials grants obtain a new access token using client credentials
  and ignore any refresh token returned by the provider.
- OIDC renewal uses the configured issuer and refresh token.
- A missing or empty refresh token in a successful renewal preserves the
  previous refresh token for password grants and OIDC. Fresh login, including
  recovery and `login(force=True)`, starts without tokens and therefore cannot
  retain a rejected or deliberately bypassed refresh token.
- Credentials are first saved through the optional persistence hook using a
  candidate configuration. Only a successful save publishes those values to
  the live configuration. Unrecovered protocol failures and cancelled requests do not
  publish token updates.

A persistence failure leaves local credentials unchanged. It cannot undo token
rotation already performed by a remote provider; interactive login may be
needed if that provider no longer accepts the previous refresh token.

`login(force=True)` acquires fresh authentication on a temporary configuration
without access or refresh tokens. It respects `interactive` and `no_browser`,
then commits all resulting secrets through the shared persistence operation.
The client mixin updates an existing HTTPX2 transport only after login succeeds.
These recovery and interaction policies remain Cuiman responsibilities when
the underlying protocol helpers are replaced by Authlib.

The current implementation retains its existing 401-triggered renewal and
single retry. It does not yet track token expiry or coordinate concurrent
renewals. Initial asynchronous login remains coordinated by the client mixin.
Static access tokens have no renewal callback and never cause automatic
interaction. See [Remote notebooks](./configuration.md#remote-notebooks).

## Remaining Authlib integration

Subsequent changes can replace the remaining OAuth/OIDC protocol helpers and
connect the launched-app proxy to its owner's Authlib client. Configuration,
interaction policy, and keyring persistence remain Cuiman responsibilities.
That change should verify:

- HTTPX2 compatibility for synchronous and asynchronous clients;
- browser authorization with PKCE and remote CLI device authorization;
- expiry metadata, refresh coordination, and the existing 401 retry policy;
- refresh-token rotation and the reviewed persistence-failure behaviour;
- Keycloak interoperability and injected-token notebook use.

The intended benefit is deletion of custom protocol and lifecycle code. Avoid
retaining a second independent token manager alongside the library. Device
authorization and notebook token-provider callbacks remain deferred. Automatic
expiry handling is currently available for Python client credentials.
