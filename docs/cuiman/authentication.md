# Authentication

Python clients, CLI login/logout, and the launched app share one authentication
lifecycle. Each Cuiman client owns one persistent HTTP client. OAuth2 and OIDC use
Authlib's `OAuth2Client` or `AsyncOAuth2Client` directly; other mechanisms use HTTPX2.
Supported mechanisms are anonymous access, JupyterHub, Basic, static tokens,
API keys, proprietary login, OAuth2 password/client-credentials grants, and OIDC
authorization code. The default `auto` selection discovers authentication;
currently only JupyterHub discovery is supported. See
[configuration](configuration.md) for provider settings and the
[CLI reference](cli.md) for command options.

For an application-specific client, create the sync client, async client, and
CLI with the same `config_type`. Its resolved configuration, including profile
identity and any keyring persistor, is retained when the launched app creates
its backend client; authentication does not fall back to another application's
defaults.

## Login and requests

Ordinary processing requests use configured credentials without prompting.
Call `client.login()` explicitly to permit credential prompts or OIDC browser
login. For `AsyncClient`, await login and all processing methods.

```python
from cuiman import Client

client = Client()
try:
    client.login()                 # Optional for already configured credentials.
    processes = client.get_processes()
    token = client.token           # Independent snapshot; does not start login.
finally:
    client.close()
```

`login(interactive=False)` prohibits interaction. `login(no_browser=True)` prints
the OIDC authorization URL. By default, login reuses available credentials and
prompts only for missing values. `login(force=True)` starts a fresh sign-in and
prompts for replacement credentials, or opens OIDC authorization again.
`login(force=True, interactive=False)` uses configured credentials for a fresh
grant without prompting; OIDC still requires interactive authorization.

The CLI uses these same controls:

```console
cuiman configure
cuiman login                 # Reuse saved credentials or collect missing values.
cuiman login --force         # Sign in again, allowing credential prompts.
cuiman login --no-browser    # Print an OIDC authorization URL when login is needed.
cuiman login --no-input      # For scripts: never prompt or open a browser.
cuiman logout
```

`--force --no-input` performs a fresh grant with supplied credentials. Missing
credentials fail with an actionable error. Authentication failures in the CLI
do not print raw provider token responses. Ordinary Python callers still receive
the native library errors.

Authlib handles grant requests, request signing, expiry, and refresh rotation.
Known expiry triggers refresh before a protected request; client credentials
can acquire another token. A token without expiry metadata is used as supplied.
An expired password/OIDC token without a refresh token requires explicit fresh
login. Rejected refresh raises the library error; it does not fall back to the
password grant. A processing-service 401 is returned as a processing API error.
Cuiman does not renew and replay that request.

OAuth uses standard bearer signing. The browser proxy filters incoming headers
and always uses the owning client's credentials.

## Runtime HTTP authentication adapters

Both `Client` and `AsyncClient` accept a native `httpx2.Auth` instance as the
constructor's `auth` argument, which also accepts an authentication
configuration model or dictionary. These are alternative selections. Omitting
constructor `auth` or passing `None` retains configured authentication; supplying
a model or dictionary keeps the existing replacement and partial-merge rules.
The adapter belongs to the running client,
is never serialized into configuration, and is used by Python calls and the
launched app through the same owned HTTP client.

```python
import httpx2
from cuiman import Client

adapter = httpx2.BasicAuth("user", "password")
client = Client(api_url="https://processing.example.org/api", auth=adapter)
try:
    processes = client.get_processes()
finally:
    client.close()
```

A client-level adapter takes precedence over configured authentication and
skips loading its keyring credentials. Configuration still needs to be valid.

With a client adapter, `login()` prepares the HTTP client. For `JupyterHubAuth`,
it also verifies that the Hub returns a usable upstream token; arbitrary adapters
are not invoked until a request is sent. `force`, `interactive`, and
`no_browser` do not initiate configured login. `login(save=True)` raises an error
because Cuiman cannot persist arbitrary adapter credentials. `client.token`
returns `None`. `logout()` closes the client without deleting overridden profile
credentials or revoking tokens. Cuiman closes its HTTP connections; it does not
call adapter-specific cleanup methods.

Cuiman adds no fallback or replay when an adapter fails or the processing service
returns 401. An adapter defines its own HTTPX2 authentication flow, which may itself
perform additional requests. Custom adapters must support the chosen client's
synchronous or asynchronous mode.

## JupyterHub discovery and required authentication

New configurations default to `auth_type="auto"`, which discovers an available
authentication mechanism. Currently only JupyterHub discovery is supported;
other mechanisms may be added in the future. If no mechanism is detected, access
is anonymous. A detected mechanism that is misconfigured or fails raises an
error instead of falling back to anonymous access or another mechanism.

Currently, `auto` looks for `JUPYTERHUB_API_URL` and `JUPYTERHUB_API_TOKEN` on the
first authenticated operation. Both absent means anonymous access. Partial or
malformed settings raise `JupyterHubAuthError`; a failed Hub lookup stops the
operation. Construction performs no network I/O. Selection is retained for that
client; create a new client after changing its environment or auth settings.

Select `Client(auth={"auth_type": "none"})` to disable discovery and use anonymous
access. Existing profiles explicitly configured with `none` remain anonymous.
`AutoAuthConfig()` and `NoAuthConfig()` are the equivalent typed configurations.
Explicit configured authentication and runtime adapters bypass discovery.

To require JupyterHub authentication, use the existing `auth` argument:

```python
client = Client(
    api_url="https://processing.example.org/api",
    auth={"auth_type": "jupyter"},
)
try:
    client.login()  # Verify that the Hub currently supplies an upstream token.
    processes = client.get_processes()
finally:
    client.close()
```

`JupyterAuthConfig()` is the equivalent typed configuration. Required Jupyter
auth errors when the environment or token is unavailable. Verification establishes token availability at that moment; it
cannot guarantee that the processing service will accept it later. Async clients
use the same policy; await `login()`, processing calls, and `close()`.

Use `configure --auth-type auto`, `none`, or `jupyter` to persist the selection
from the CLI. Set `EOZILLA_AUTH__AUTH_TYPE=auto` (or an application's own prefix)
for an environment override. `login` verifies availability for detected or
required Jupyter auth. Hub credentials and upstream tokens are never written
to profiles or the keyring.

## Explicit JupyterHub authentication

Use `JupyterHubAuth` when your Hub exposes an upstream access token accepted by
your processing service:

```python
import os
from cuiman import Client
from cuiman.api.auth import JupyterHubAuth

client = Client(
    api_url="https://processing.example.org/api",
    auth=JupyterHubAuth(
        hub_api_url=os.environ["JUPYTERHUB_API_URL"],
        hub_api_token=os.environ["JUPYTERHUB_API_TOKEN"],
    ),
)
try:
    processes = client.get_processes()
finally:
    client.close()
```

The same adapter works with `AsyncClient`; await its processing calls and
`close()`. These arguments are explicit. Constructing an adapter does not contact
the Hub. `login()` checks token availability using only the Hub endpoint; each
later processing request still retrieves a fresh token.

Before each authenticated processing request, the adapter calls
`<hub_api_url>/user` with the Hub credential, reads `auth_state.access_token`,
and signs the processing request with that upstream bearer token. Hub and
processing requests use the owner's existing HTTP client and effective request
timeout. Processing headers, cookies, query parameters, and body are not copied
to the lookup. Tokens are not cached or persisted by the adapter. The Hub owns
refresh; Cuiman does not use refresh tokens or implement an expiry timer.

The deployment must enable `Authenticator.enable_auth_state`, configure
`JUPYTERHUB_CRYPT_KEY`, and grant `admin:auth_state!user` to the user and server
roles. Use OAuthenticator's refresh support (17.2 or later), with a nonzero
`auth_refresh_age` and suitable provider refresh credentials. See the official
[JupyterHub token-retrieval setup](https://oauthenticator.readthedocs.io/en/latest/how-to/refresh.html#refreshing-tokens-from-user-sessions)
for the complete role configuration. A running notebook alone does not establish
that these permissions or token capabilities are available.

Only attach the adapter to a client whose processing service is a trusted
recipient of the upstream token. Use the Hub API base URL, including any prefix,
not a browser login URL. HTTPS is recommended; HTTP is allowed for trusted private
Hub networks. Lookup redirects are rejected; retain HTTPX2's default of not
following redirects to avoid contacting redirect targets before that check.

Missing or malformed auth state raises `JupyterHubAuthError` with setup guidance
and no response-body contents. HTTP status and network failures use the existing
Cuiman `TransportError` wrapper with the underlying HTTPX2 exception as its cause.
All lookup failures stop the processing request. A processing-service 401 is
returned without token recovery or request replay. A later caller-initiated
request performs a fresh lookup. Logout closes the Cuiman owner without signing
out of JupyterHub.

## JupyterHub and the launched app

The app uses the same authentication selection and HTTP session as its owning
Python client. When JupyterHub auth is selected, the launch-code exchange
verifies that the Hub can provide an upstream token before creating a browser
session.
Every later app request retrieves the current token again, just like Python
requests. Changes made by the Hub's refresh mechanism therefore reach both.

Hub credentials and upstream tokens stay in Python. The browser receives an
opaque HttpOnly session cookie; its Authorization header and cookies are not
forwarded to the Hub or processing service. A failed lookup stops the processing
request and returns a generic app error without provider response details.
A failed launch check leaves the unexpired launch code available for retry.
Processing requests are never replayed after an authentication failure.

Stopping an app that borrows a Python client leaves that client usable.
Closing or logging out of the client closes its HTTP session and makes later
app requests fail. A standalone app server closes its own client when stopped.
For `auto` and `jupyter`, logout does not access the keyring or sign the user
out of JupyterHub, even before the first request. Start a new client to resume.

Authentication discovery is independent of `show_app(proxy="auto")`, which
controls how the notebook browser reaches the local app server through
`jupyter-server-proxy`.

## Token configuration and storage

OAuth2 and OIDC accept one `oauth_token` mapping as bootstrap credentials. Keep
the complete token, including absolute `expires_at`, to preserve expiry and
refresh behavior. The running Authlib client owns subsequent updates;
`client.config.auth.oauth_token` is not a live token view. Read `client.token`.
For OIDC, the snapshot also retains `_cuiman_nonce` to validate a nonce returned
with refreshed ID tokens after restarting the client.

Cuiman writes public settings only to configuration files. Passwords and complete tokens
are saved in the OS keyring, scoped to configuration-file path and processing
API URL. A configuration loaded from a named file retains that profile when
passed to `Client(config=config)` or `AsyncClient(config=config)`, including for
explicit saving and logout. There is no plaintext-file fallback.

Sharing a configuration profile does not share a running client or coordinate
refresh-token rotation between independent clients or processes. Use the same
client for related Python and app requests that need one live session.

An existing keyring source receives optional token updates. If that save fails,
Cuiman warns with `CredentialStorageWarning` and keeps the live token usable.
`client.login(save=True)` explicitly saves credentials to the client's profile;
a failed save raises `SecretStoreError`. A successful explicit save also enables
subsequent refresh updates to that profile. CLI login uses this same operation and
does not report success when saving fails. Environment/Python credentials can
therefore be explicitly saved without first loading them from the keyring.

`client.logout()` revokes an OIDC refresh token (or access token) if discovery
advertises revocation, removes local credentials, and closes the client. Local
removal and closure still run if revocation fails. Other credential-based
mechanisms remove local credentials without a provider revocation operation.
Runtime adapters, `auto`, and `jupyter` only close the local client; they do not
delete profile credentials or sign out of JupyterHub. CLI logout uses this method.
Create a new client after close or logout.

## OIDC and the launched app

OIDC uses Authlib's authorization URL, S256 PKCE, callback-state validation,
code exchange, and refresh. Cuiman provides the temporary loopback listener and
requires an exact discovery issuer match, including trailing slashes, and HTTPS
provider endpoints without embedded credentials or fragments. Register a native
client redirect URI pattern for `http://127.0.0.1:<port>/callback` with your
provider; Cuiman chooses a temporary port. Repeated security parameters in the
callback are rejected before the authorization response reaches Authlib.

Authlib and joserfc validate ID-token signatures, issuer, audience, nonce, and
timestamps. Cuiman accepts asymmetric signatures only and fetches the provider's
JWKS for each ID-token validation, including refresh, to support signing-key
rotation. Raw Authlib HTTP clients do not validate ID tokens automatically.
Initial login requires an ID token; refresh may omit it. An invalid ID token
invalidates the new live token before it can be saved or used for a request.

`client.show_app()` lends the app its live requester. Browser sessions contain
opaque local identifiers, not upstream token snapshots. Requests from all browser
sessions use the same owner, so they observe token refresh without signing in
separately. Launch capabilities, HttpOnly cookies, origin checks, fixed upstream
paths, and header filtering remain enforced by the local proxy.

A synchronous owner handles app requests in worker threads with serialized
access. An asynchronous owner stays on its original running event loop; the app
dispatches requests to that loop. Both modes currently serialize requests on
one owner. Call `AsyncClient.show_app()` from that loop
and keep it running while using the app. Stopping the app does not close a
borrowed client. Standalone `cuiman.app.serve(config, store)` owns an asynchronous
client and closes it with the server lifespan. Closing an owner makes further
app requests fail; the proxy does not create a replacement session.

## Concurrent calls and cancellation

Calls on one owner are serialized. Overlapping API and browser requests share
one token refresh and its rotated credentials. `close()` waits for an active
request before closing connections; standalone app shutdown closes its owner
through the same operation.

Cancelling an async login, close, or logout while it waits for the owner lock
leaves the active request and credentials unchanged. Once logout starts,
revocation failure or cancellation still removes local credentials and closes
the owner before queued requests can run. Cancelling OIDC validation discards
the unverified token before a processing request or credential save can use it.

Cancelling an asynchronous app request propagates to its owner's HTTP operation.
A synchronous request already running in a worker thread can finish after its
caller stops waiting; closing that owner waits for the worker. Cancellation does
not undo a request already received by a provider. If a token response is lost
and later refresh fails, use explicit fresh login; Cuiman does not replay the
processing request or fall back to a password grant.

## Configuration cut

OAuth2/OIDC no longer accept separate `access_token` or `refresh_token` fields,
`use_bearer`, or `access_token_header`. Both require a client ID. Remove obsolete
fields from existing OAuth configuration, then sign in again to replace old
keyring records. Static `token` and proprietary `login` retain their access-token
and custom-header settings; API keys retain their configured header.

Static `token` and proprietary `login` also remove `use_bearer` and the CLI
`--use-bearer` switch. Omit `access_token_header` for Bearer signing, or supply a
custom header name for a raw token. Remove the old default `X-Auth-Token` field
when converting a Bearer configuration; keep the intended header when converting
a custom-header configuration. `configure` asks one header question and rejects
options that do not apply to the selected authentication type. API-key headers
can be supplied with `configure --api-key-header`.

Files that cannot be parsed or validated against the configured model are
rejected with "Deprecated or illegal configuration file, please run the
'configure' command." Valid files are accepted without legacy-field detection.
`configure` can
recreate them from defaults without translating old settings or copying secrets.
Supply the provider settings again and log in. Failed or cancelled configuration
leaves the existing file untouched. Current public profiles retain their settings
as prompt defaults; selecting another authentication type discards unrelated
provider defaults.

The old one-shot OAuth/OIDC helpers, `TokenResult`, configuration renewal
factories, password subclasses, and transport renewal callbacks are removed.
Use the shared client lifecycle instead of assembling a separate login engine.

## Implementation boundaries

Cuiman follows Authlib's
[HTTP client programming model](https://docs.authlib.org/en/stable/oauth2/client/http/httpx.html):
one persistent client performs both token exchanges and processing requests.
The web-framework session registry is unnecessary for this outbound client and
would introduce another ownership model. Authlib owns OAuth request encoding,
token parsing, expiry, refresh rotation, signing, PKCE/code exchange, and
revocation. Cuiman supplies initial grant preparation, prompts and the loopback
listener, discovery trust checks, library-based ID-token validation, keyring
storage, and app-proxy security.

`ClientMixinBase` shares credential selection, client setup, grant preparation,
validation policy, and persistence. The sync and async mixins perform native I/O
and manage locking, cancellation, closure, and app dispatch. The processing
transport converts requests and responses; it does not manage OAuth recovery.
There are no Cuiman OAuth subclasses or separate live token managers.

The following integration details were verified against Authlib 1.8.0 and should
be retained when updating the dependency:

- Set `grant_type` and `token_endpoint` metadata on the persistent client, using
  OIDC discovery for its endpoints, so native expiry handling can refresh or
  reacquire tokens. Use `request` for protected calls; inherited `send` bypasses
  that expiry handling.
- Explicit `fetch_token` does not call `update_token`, so Cuiman saves the initial
  result explicitly. Automatic refresh uses the callback; the async client needs
  an async callback.
- Authlib installs a new token before calling the storage callback. Optional
  storage failure keeps that live token and warns; persistence is not a
  save-before-publication transaction. Rolling back local state cannot undo a
  provider's refresh-token rotation.
- Use Authlib's token parsing and refresh-token retention behavior. A returned
  refresh token can take precedence over reacquiring a client-credentials grant.
  Add provider-specific adaptations only for a demonstrated requirement.

These details follow the pinned
[OAuth token lifecycle](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/client.py)
and [HTTPX integration](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/httpx_client/oauth2_client.py).
Regression tests exercise actual Authlib clients with mock HTTP responses and
fake keyring backends, including rotation, ownership, cancellation, and profile
isolation. They do not establish live-provider or OS-keyring interoperability.
Device authorization is not implemented.
