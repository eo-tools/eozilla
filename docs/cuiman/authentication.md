# Authentication

Python clients, CLI login/logout, and the launched app share one authentication
lifecycle. Each Cuiman client owns one persistent HTTP client. OAuth2 and OIDC use
Authlib's `OAuth2Client` or `AsyncOAuth2Client` directly; other mechanisms use HTTPX2.

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

OAuth uses standard bearer signing. Python callers can override request auth
with the HTTPX2 `auth` argument or an explicit `Authorization` header. The browser
proxy filters incoming headers and always uses the owning client's credentials.

## Token configuration and storage

OAuth2 and OIDC accept one `oauth_token` mapping as bootstrap credentials. Keep
the complete token, including absolute `expires_at`, to preserve expiry and
refresh behavior. The running Authlib client owns subsequent updates;
`client.config.auth.oauth_token` is not a live token view. Read `client.token`.
For OIDC, the snapshot also retains `_cuiman_nonce` to validate a nonce returned
with refreshed ID tokens after restarting the client.

Configuration files contain public settings only. Passwords and complete tokens
are saved in the OS keyring, scoped to configuration-file path and processing
API URL. A configuration loaded from a named file retains that profile when
passed to `Client(config=config)` or `AsyncClient(config=config)`, including for
explicit saving and logout. There is no plaintext-file fallback.

An existing keyring source receives optional token updates. If that save fails,
Cuiman warns with `CredentialStorageWarning` and keeps the live token usable.
`client.login(save=True)` explicitly saves credentials to the client's profile;
a failed save raises `SecretStoreError`. A successful explicit save also enables
subsequent refresh updates to that profile. CLI login uses this same operation and
does not report success when saving fails. Environment/Python credentials can
therefore be explicitly saved without first loading them from the keyring.

`client.logout()` revokes an OIDC refresh token (or access token) if discovery
advertises revocation, removes local credentials, and closes the client. Local
removal and closure still run if revocation fails. Other mechanisms remove local
credentials without a provider revocation operation. CLI logout uses this method.
Create a new client after close or logout.

## OIDC and the launched app

OIDC uses Authlib's authorization URL, S256 PKCE, callback-state validation,
code exchange, and refresh. Cuiman provides the temporary loopback listener and
requires an exact discovery issuer match and HTTPS provider endpoints. Authlib
and joserfc validate ID-token signatures, issuer, audience, nonce, and timestamps.
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

Incompatible old configuration files are recreated from defaults by `configure`;
there is no legacy settings translator. Supply the provider settings again and
log in. Current public profiles retain their settings as prompt defaults.

The old one-shot OAuth/OIDC helpers, `TokenResult`, configuration renewal
factories, password subclasses, and transport renewal callbacks are removed.
Use the shared client lifecycle instead of assembling a separate login engine.
