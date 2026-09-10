# Authlib research for Cuiman

Date: 2026-09-09. Target: Authlib **1.8.0**, using its HTTPX2 integration.
This is design research, not implementation. No dependency changes, installations,
provider logins, or production experiments were performed. Read alongside
`HANDOVER_AUTHLIB.md` and the design proposal.

The conclusions below distinguish inspected library behavior from proposed Cuiman
policy. Source links use the version tag and actual source-file line numbers;
browser extraction line numbers differ from GitHub line numbers. Several public
source files required a direct read because the browser cache could not fetch them.

The compatibility policies proposed in this historical research are superseded
by [AUTHLIB_DESIGN.md](AUTHLIB_DESIGN.md). Current implementation and verification
status are recorded in [HANDOVER_AUTHLIB.md](HANDOVER_AUTHLIB.md).

## Integration fit

Authlib exposes synchronous `OAuth2Client` and asynchronous `AsyncOAuth2Client`
through `authlib.integrations.httpx_client`. Its documentation demonstrates using
these as the HTTP clients for protected requests, reusing them, and closing them
with synchronous/asynchronous context managers.
[HTTPX2 client documentation](https://docs.authlib.org/en/stable/oauth2/client/http/httpx.html).

The v1.8.0 compatibility module imports HTTPX2 preferentially and falls back to
HTTPX with a deprecation warning. Thus the existing HTTPX2 checkpoint matches the
selected integration; this finding does not prove compatibility of every dependency
in Cuiman's environment.
[Compatibility module](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/httpx_client/_compat.py#L1-L18).

Starlette's integration is a web login abstraction: a registry of remote apps,
redirect routes, callback requests, and automatic ID-token parsing. FastAPI uses
that same integration. These capabilities suit browser users logging into a web
application, but do not by themselves justify moving a desktop/CLI/library client
into a web session model.
[Starlette integration](https://docs.authlib.org/en/stable/oauth2/client/web/starlette.html),
[FastAPI integration](https://docs.authlib.org/en/stable/oauth2/client/web/fastapi.html).

The framework async client actually creates a context-managed OAuth HTTP client
per request and injects a supplied/fetched token. Metadata fetching is also provided
there. **Design inference:** borrowing that integration just for discovery or OIDC
would introduce a second lifetime model; use persistent HTTP clients for Cuiman's
outbound API work, with narrowly scoped discovery/validation helpers.
[Framework async source](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/base_client/async_app.py#L76-L151).

## Core token behavior verified in v1.8.0

- `client.token` delegates to `token_auth.token`; assigning it normalizes the token.
- `parse_response_token` parses JSON/OAuth errors and assigns the live token.
  Refresh then retains an omitted refresh token and calls `update_token`.
  Ordinary `fetch_token` does **not** call that callback.
- Expiry handling refreshes when both refresh token and endpoint exist; otherwise
  client-credentials metadata enables reacquisition. A returned refresh token takes
  precedence even for client credentials.
- Configure `grant_type` in constructor metadata: explicitly passing it to a fetch
  does not reliably establish that metadata. Configure `token_endpoint` too.
- No sync refresh lock, resource-401 recovery, or password fallback appears in
  these lifecycle methods. Explicit `refresh_token` does not acquire a lock.
- With a secret, default endpoint auth is Basic; without one, it is `none`.
- Response compliance hooks run before parsing; protected-request hooks are
  delegated to token auth. There is no documented persistence-before-assignment
  hook in these paths.

[Core token property](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/client.py#L136-L142),
[fetch and refresh](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/client.py#L185-L320),
[parsing and update ordering](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/client.py#L414-L465).

## HTTPX2 behavior and concurrency

`request` and `stream` perform token checks, expiry handling, and token signing.
Supplying explicit HTTP auth or `withhold_token=True` bypasses that OAuth path.
Token endpoint calls supply explicit client auth and therefore avoid recursive
expiry checks. Direct inherited `send` is not a demonstrated expiry-aware entry
point: route Cuiman through `request`/`stream`.

Async `ensure_active_token` uses an AnyIO lock, covering refresh/reacquisition and
the awaited update callback. It tests current `self.token` expiry but obtains
refresh credentials from its argument. Explicit fetch/refresh bypass that lock;
separate clients never share it. Its callback is awaited, so provide an async
callback even though prose documentation suggests broader callback support.

These paths assign the live token before persistence. Callback failure prevents
that request from proceeding but does not restore the old token. No cancellation
shield or remote-rotation rollback is provided.

[Async request, stream, and lock](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/httpx_client/oauth2_client.py#L112-L155),
[async token operations](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/httpx_client/oauth2_client.py#L157-L205),
[sync request and stream](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/httpx_client/oauth2_client.py#L258-L287).

## Small compatibility adapters

Authlib's token auth defaults missing `token_type` to bearer. Protected-request
hooks run **after** bearer signing, making custom header relocation possible
without a second bearer renderer. Only bearer is supported by the default signing
map. Client-secret POST is built in. The `none` endpoint-auth encoder still appends
`client_id`, even if its value is `None`; Cuiman's password-without-client-ID case
needs a no-op endpoint-auth callable, rather than assuming `none` means no fields.
[Token signing and endpoint authentication](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/auth.py#L19-L111).

The documented client-auth callable receives the client, method, URI, headers,
and body and returns the latter three values. Authlib also supports response and
protected-request compliance hooks. Password acquisition and explicit refresh
are public operations; recovery policy remains application work.
[HTTP client extension points](https://docs.authlib.org/en/stable/oauth2/client/http/index.html#client-authentication).

`OAuth2Token` computes an absolute `expires_at` from usable `expires_in` when
necessary. Missing/noninteger expiry causes `is_expired` to return `None`, so an
injected token without expiry is not proactively rejected. Persist the normalized
absolute expiry; restoring only an old duration could extend perceived lifetime.
[Token wrapper](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/rfc6749/wrappers.py#L4-L35).

## PKCE and OIDC boundary

The HTTP client supports authorization URL construction, state checking during
authorization-response parsing, and S256 PKCE when Cuiman supplies and retains the
verifier. Cuiman must retain the expected state and pass it back explicitly; it
also generates/retains a nonce. Raw HTTP token fetching does not automatically
validate an ID token. The official HTTP documentation demonstrates separate
`joserfc.jwt.decode` and `CodeIDToken` validation.
[PKCE and OIDC HTTP documentation](https://docs.authlib.org/en/stable/oauth2/client/http/index.html#add-pkce-for-authorization-code),
[OIDC validation documentation](https://docs.authlib.org/en/stable/oauth2/client/http/index.html#oauth-2-openid-connect).

The framework OIDC implementation illustrates the necessary orchestration:
trusted issuer expectations, client ID and nonce parameters, provider algorithm
metadata, JWKS retrieval, a retry for unknown key ID, JWT signature decoding, then
claims validation. Its metadata loader alone does not prove that discovery issuer
matches Cuiman's configured issuer. Preserve that explicit application check.
[Async OIDC implementation](https://github.com/authlib/authlib/blob/v1.8.0/authlib/integrations/base_client/async_openid.py#L16-L87).

`CodeIDToken` inherits checks for essential claims, nonce, authorized party, and
access-token hash when supplied. Supplying the expected issuer/audience and
calling validation remain necessary; merely decoding a JWT is insufficient.
[OIDC claims implementation](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oidc/core/claims.py).

## Design implications to review

The following are recommendations, not library guarantees:

1. Make the persistent Authlib HTTP client's token the sole live OAuth authority.
   Configuration and keyring hold initialization/persistence snapshots. A thin
   Cuiman subclass can retain application login/recovery policy while delegating
   grant requests, token parsing, expiry, refresh, and signing to Authlib.
2. A Cuiman transition gate may coordinate initial/forced login, explicit recovery,
   and delegated expiry handling. Acquire it only at outer entry points; callbacks
   and inner fetch/refresh calls must not reacquire it. Delegate expiry using the
   current token **after** acquiring the gate. Keep resource I/O outside it.
3. Coalesce overlapping 401 recovery by comparing the token actually signed on
   the failed request with the current token. A snapshot taken before the request
   can be stale. Preserve the existing single replay and only recover password
   grants for the intended OAuth rejection, not arbitrary network/storage errors.
4. Each client needs one execution owner. Cross-thread/event-loop proxy calls must
   reach that owner, or an explicit ownership transfer must quiesce it. Merely
   sharing a config or keyring record does not coordinate rotating refresh tokens.
5. Prefer reviewing a memory-first persistence contract: retain the provider's
   latest token, surface storage failure, and state that durable storage remains
   stale. The current strict local rollback guarantee requires extra transaction
   machinery and still cannot undo provider rotation. Neither option makes a
   network exchange and keyring write atomic. Cancellation after provider success
   but before response receipt remains ambiguous; shielding local save can only
   narrow the later cancellation window.

## Evidence limits and next experiment

These are inspected source/design conclusions. They have not been verified
against a running Cuiman/Authlib combination, real Keycloak, rotating-token
concurrency, keyring failures, or cross-loop proxy use. The first implementation
step should therefore be a bounded compatibility/lifecycle experiment with fake
HTTP responses and fake persistence, followed by review. Check actual callback
ordering, client-credentials reacquisition, omitted token type, no-client-ID form
encoding, custom headers, expiry without metadata, one refresh under concurrency,
explicit recovery coordination, and cancellation. No production implementation
or dependency change is implied by this research note.
