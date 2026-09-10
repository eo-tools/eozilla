# Authentication lifecycle

Cuiman's Python clients use persistent Authlib HTTPX2 clients for OAuth2
`client_credentials` and password grants. OIDC, CLI login, and the launched-app proxy
currently retain the shared session helpers while Authlib integration proceeds
in separately reviewed steps. Ordinary API calls never prompt or open a browser.

## OAuth2 in Python clients

For `Client` and `AsyncClient`, Authlib owns the live token and sends authenticated
API requests through the same HTTP client used to obtain it. It tracks expiry and
automatically obtains a new client-credentials token before an expired token is
used. Provider-supplied refresh tokens are ignored for client credentials. Requests still
retry at most once after HTTP 401 by obtaining another client-credentials token.
Without expiry metadata, an injected access token can be used until rejected.

Password grants use the same persistent lifecycle. Initial login can use an
existing access token, refresh-only credentials, or a username and password.
Authlib refreshes tokens before known expiry, retaining a refresh token when the
provider omits it or returns an empty/null value. A fresh password grant,
including `login(force=True)`, replaces the whole token and never inherits the
old refresh token. Password grants can omit the client ID; configured client
credentials are sent in the request body.

After a resource 401, password authentication refreshes and replays at most once.
An HTTP 400 `invalid_grant` response to refresh permits one fresh password grant
using available credentials. When there is no refresh token, known expiry or a
resource 401 also permits password reacquisition. Missing credentials raise
`LoginRequiredError`; ordinary requests never prompt. Other provider, network,
or storage errors do not trigger password fallback. Explicit login may prompt
for a username and password, and a failed grant leaves the previous live token
available. As with client credentials, token responses use Authlib's typed OAuth
errors; HTTP failures during API requests retain Cuiman's transport error mapping.

`client.login()` prepares this client without making an API request;
`client.login(force=True)` obtains a fresh token. Use `await` for asynchronous
login, API calls, and `close()`. Close the client even if only login was called,
or login failed. Generated `Client`/`AsyncClient` classes delegate runtime
initialization and closing to their handwritten mixins; their source is
`tools/gen_client.py`.

Read `client.token` for an independent snapshot of the live token, including
`expires_at`. It returns `None` before initialization and never initiates login.
The token is a credential: do not save it in notebook output or logs. For this
OAuth2 lifecycle, `client.config.auth.access_token`, `refresh_token`, and
`oauth_token` are **initial values**,
not a live token interface. Use `client.token` instead of config token/header
properties after login. OIDC and other authentication mechanisms have not yet changed
their token interface.

Custom token headers remain supported. Explicit per-request `auth` or an override
of the configured token header bypasses Authlib signing and the 401 renewal
callback for that request.

When a persistence hook is configured, Cuiman saves a complete token snapshot,
including its absolute expiry, under the string-valued keyring field
`oauth_token`. Existing access/refresh-token records still load. An explicitly
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

Authlib coordinates automatic async refresh when a refresh token is present.
Password reacquisition without a refresh token is verified for sequential use.
This step does not add coordination across explicit login, 401 recovery, threads,
or separate clients, or comprehensive cancellation handling.
The launched-app proxy still uses its legacy authentication path and does not
borrow the Python client's Authlib session yet.

## Responsibilities

The table below describes the remaining session-based authentication paths.
For Python OAuth2, `auth.oauth2_client` constructs Authlib clients and adapts
provider responses and persistence. Its password subclasses add explicit login
and narrow fallback policy; Authlib handles protocol requests, token parsing,
expiry decisions, refresh rotation, and signing.

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

When a legacy session receives a saved `oauth_token` snapshot, it consumes that
snapshot once into its own access/refresh fields. Later legacy saves omit the old
snapshot so they cannot leave stale expiry or refresh metadata beside new tokens.
These sessions do not read or share a Python client's live Authlib token. Avoid
using configuration renewal callbacks to renew an active Python OAuth2 client;
use the client's API methods or explicit login. CLI login still requires durable
storage and reports save failures as errors.

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
expiry handling is available for Python OAuth2 password and client-credentials grants.
