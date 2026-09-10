# Authlib integration for Cuiman: clean replacement

Updated: 2026-09-10. Status: slice 1 implemented for review; supersedes the incremental,
compatibility-preserving migration proposed here previously.

Implementation sequence: [three-slice plan](AUTHLIB_PLAN.md).

## Objective and constraints

Cuiman is a processing-system client. Authlib should own its OAuth protocol and
live token lifecycle. Reduce Cuiman's production authentication implementation
and make authentication easier to configure and use. Backward compatibility is
not required. The user's question about preserving `config.py`, the Client
interface, and the CLI was a request to explain the plan, not a preservation
constraint. Useful deletions and interface changes are explicitly welcome.

The current recommendation is to retain the configuration module's role, the
processing-oriented Client interface, and the familiar CLI workflows (`configure`,
`login`, `logout`). These are useful concepts. Their existing fields, helper
methods, signatures, and options are not frozen. Simplify them where doing so
removes redundancy or user effort; explain the benefit and resulting behaviour.
Avoid gratuitous renaming and avoid removing a useful capability merely to save
a few implementation lines.

Keep review checkpoints, but choose implementation steps by complete
responsibility, not by grants that leave another implementation behind. Review
the coherent replacement and its user-visible changes together; do not invent a
separate permission requirement for every field deletion. The password slice at
`41181d3` is an intermediate implementation to replace.

Preserve useful sign-in capabilities: client credentials, password grants where
needed by a processing service, and browser-based authorization code with PKCE.
Basic, static tokens, API keys, and proprietary login remain separate non-OAuth
mechanisms. Removing a compatibility interface does not require removing these
capabilities or weakening browser-proxy security.

## Authlib is the runtime

Use persistent `authlib.integrations.httpx_client.OAuth2Client` and
`AsyncOAuth2Client`, with the pinned Authlib 1.8.0 / HTTPX2 integration. Construct
one HTTP client per Cuiman client and use it for token requests and processing API
requests. Use ordinary HTTPX2 clients for non-OAuth authentication.

Start with direct Authlib clients. No Cuiman OAuth subclasses, replacement token
model, expiry calculation, token manager, or grant-recovery state machine.

Authlib owns:

- OAuth request encoding and token endpoint authentication;
- authorization URL construction, PKCE challenge construction, and callback-state
  validation during authorization-code exchange;
- token response parsing and OAuth error types;
- live access/refresh token state and absolute expiry;
- automatic refresh and client-credentials reacquisition;
- refresh-token rotation and protected-request signing;
- token revocation protocol operations.

Cuiman supplies configuration, the initial explicit grant, local interaction,
credential storage callbacks, and processing-specific response conversion.
Explicit `fetch_token` requires an explicit save afterward; automatic token
updates use Authlib's `update_token` callback.

Use `request` as the common HTTP entry point. Do not maintain copied OAuth headers
or send protected API requests through an independent HTTP session.

Sources: [HTTPX integration](https://docs.authlib.org/en/stable/oauth2/client/http/httpx.html),
[HTTP client programming model](https://docs.authlib.org/en/stable/oauth2/client/http/index.html),
[pinned token lifecycle source](https://github.com/authlib/authlib/blob/v1.8.0/authlib/oauth2/client.py).

## Adopt library behaviour

The replacement proposes the following library behaviour. Include these changes
in the design review and user documentation:

- A resource 401 is returned as a processing API error. Delete automatic renewal
  and replay from the transport and proxy. Known token expiry is handled by Authlib
  before the request, without replaying a processing operation.
- A rejected refresh propagates the library/provider error. The caller can perform
  explicit fresh login. Delete automatic refresh-to-password fallback.
- Password authentication without a refresh token can require explicit login after
  expiry. Delete the special automatic password-reacquisition path.
- Accept Authlib's refresh-token retention and response parsing behaviour. Remove
  adapters that reinterpret empty/null refresh tokens or preserve old exception
  shapes solely for compatibility.

Simplify OAuth2/OIDC configuration to one complete `oauth_token` mapping and
provider settings. Remove their separate `access_token` and `refresh_token`
inputs: users should not have to understand precedence among three overlapping
token representations. Static-token authentication retains its `access_token`.
Do not introduce aliases, dual-format writes, or a compatibility bridge merely
to preserve the deleted OAuth fields.

Use Authlib's supported token endpoint authentication methods, configured from
the provider settings. Prefer standard OAuth bearer signing. Retain a custom
OAuth token-header setting or a no-client-ID adapter only if an actual supported
processing provider requires it; these are not reasons to retain a token manager.
Static tokens and API keys can keep their purpose-specific custom headers.

Retain a provider-specific compliance hook only when an actual supported provider
requires it. The client-credentials refresh-token discard can remain as a small,
explicit grant-policy hook if needed to ensure Authlib reacquires that grant.
Do not grow a generic provider registry for hypothetical deviations.

## Small Cuiman interface

The user-facing authentication operations are client construction, `login`,
`token`, `logout`, and `close`. Existing processing operations remain the main interface.
Sync/async variants differ in I/O syntax, with shared configuration and policy.

`ClientMixinBase` implements credential selection, HTTP client construction,
grant preparation, discovery acceptance, ID-token validation policy, persistence,
and request options once. The sync/async mixins execute native I/O and handle
their locks, cancellation, closure, and app dispatch. They do not contain separate
implementations of these decisions. No custom coroutine runner or OAuth subclass
is introduced to remove the remaining I/O syntax differences.

- Authentication configuration contains bootstrap credentials and provider
  settings. Remove redundant OAuth token fields, OAuth header-generation methods,
  and renewal-callback factories. The runtime has one authoritative Authlib token
  mapping. Configuration does not own a live OAuth session.
- `login()` prepares the client's own HTTP runtime. `login(force=True)` performs a
  fresh grant. Explicit interaction is controlled here. Ordinary processing and
  proxy requests never prompt or open a browser.
- `client.token` returns an independent snapshot of the runtime's OAuth token.
  There is no live token interface on `client.config.auth`.
- `close()` closes the owned HTTP runtime. Login without a processing API call has
  the same lifetime. A closed runtime is not silently recreated for a proxy call.
- The HTTP transport converts processing models to requests and responses to
  processing models/errors. It contains no grant selection or token recovery.

Change generated structure in `tools/gen_client.py` and regenerate both clients
when needed. Keep useful processing operations and familiar client workflows;
simplify authentication-specific arguments or methods when justified. Keep
authentication implementation out of generated endpoint methods.

## One implementation for all callers

Python processing calls and proxy requests use their owner's authenticated
request method. The proxy retains an authorization capability to use that owner;
it does not retain credentials or token/header snapshots per browser session.

For a synchronous Python owner, proxy work runs through a worker using that same
client. Serialize access where needed to prevent concurrent transitions on the
sync Authlib runtime. For an asynchronous owner, submit proxy requests to its
running owner loop. The loop must outlive the launched app. Use standard asyncio
or AnyIO primitives; do not build a background event-loop service or a registry
of independently synchronized token managers.

A standalone app server owns a client for its lifespan. A launched app borrows
its Python client's requester. Stopping the app does not close a borrowed client;
closing the owner makes further proxy work fail without exposing credentials.
Make these ownership rules explicit and test them at the request/close interface.

CLI login constructs the same Cuiman client, performs explicit login, saves its
result, and closes it. It does not execute a separate OAuth protocol implementation.
CLI logout delegates token revocation to Authlib where supported and removes local
credentials. Ordinary CLI processing commands already use the Python client.

Preserve the existing launch capability, HttpOnly cookie, origin checks, fixed
upstream host/path validation, and browser-header filtering. Those protect local
proxy access; they are not an OAuth token lifecycle to move into Authlib.

## Local concerns that remain

**Storage.** Keep the existing OS-keyring implementation and configuration-profile
selection. Save the complete Authlib token mapping at a small storage callback.
Keep configuration input and serialization consistent with the simplified models.
Persist one complete token snapshot without live-token reconciliation or dual
token managers. Expected optional save failures
warn while the live token remains usable. Explicit CLI saving must report failure.
Do not implement save-before-publication transactions, rollback, or retry queues.

**Interaction.** Keep credential prompts and loopback callback server lifecycle.
The callback passes an authorization-response URL to Authlib rather than parsing
OAuth code/state/errors and constructing token requests itself. Reject ambiguous
repeated security parameters before passing the response to Authlib. Cancellation
must release the local listener; it cannot undo a remote token exchange.

**OIDC.** Retain issuer and HTTPS endpoint checks for discovered metadata. Use the
persistent client's metadata rather than a parallel discovery/session object.
Use Authlib and joserfc for ID-token signature and claims validation, including
issuer, audience, nonce, and time; raw Authlib HTTP clients do not perform that
validation automatically. Do not copy the web framework's entire session registry
or treat unvalidated ID-token claims as identity. A new authorization-code OIDC
login requires a valid ID token; refresh can omit one.

**Non-OAuth.** Basic authentication uses HTTPX2's implementation. Static/API-key
headers remain small configuration adapters. Proprietary login stays isolated
from OAuth, returning the token it needs without an OAuth-shaped `TokenResult`
wrapper or shared OAuth session machinery.

## Concrete deletion list

| Current implementation | Replacement |
| --- | --- |
| `api/auth/session.py`, including resolve/renew/commit/rollback and snapshot restore | Initial preparation on the owned HTTP runtime; Authlib handles subsequent OAuth lifecycle |
| `api/auth/oauth2.py` and `oauth2_async.py` | Authlib fetch/refresh methods |
| Password subclasses in `api/auth/oauth2_client.py` | Direct Authlib clients and explicit login |
| OAuth `TokenResult` conversion and one-shot public OAuth exports | Authlib token mapping; remove those public helpers |
| Handwritten OIDC authorization, PKCE challenge, code-exchange, refresh and revocation protocol helpers; `oidc_async.py` | Authlib methods, retaining local callback/discovery trust checks |
| Config OAuth header generation and renewal-callback factories | Bootstrap settings; Authlib request signing |
| Transport renewal callbacks, OAuth header snapshots, override detection, 401 replay | Authenticated HTTP request and processing-response conversion |
| Proxy `_AppSession.headers`, header resolution, refresh/replay, per-request HTTP client creation | Borrowed requester; a set of authorized browser sessions |
| Separate CLI OAuth acquisition and token publication | Same client login plus explicit durable save |
| Separate OAuth access/refresh inputs, precedence rules, and snapshot/config reconciliation | One complete OAuth token mapping |

Remove tests that exist only to freeze deleted helper graphs or compatibility
semantics. Replace them with HTTP-boundary tests using actual Authlib clients.
Retain meaningful processing, keyring, configuration isolation, callback, and
proxy security tests.

## Completion and evidence

The next implementation must move every OAuth consumer off the old lifecycle and
remove the replaced implementation in the same reviewed change. A temporary
working-tree migration is fine; do not declare a grant-by-grant partial replacement
a successful simplification while the legacy token manager remains.

Show net production changes against the committed pre-password checkpoint, with
tests and documentation counted separately. Require an actual reduction and fewer
independent lifecycle paths; a smaller file that hides equivalent machinery in
more wrappers is not success. Do not sacrifice issuer/state checks, credential
isolation, or processing functionality merely to improve a line count.

Validate standard Authlib behaviour with mock token/resource endpoints, sync/async
clients, fake expiry, keyring callbacks, explicit login, and proxy ownership.
Use the Pixi checks, Cuiman coverage, workspace tests, and docs build. State any
remaining provider and concurrency limits. No real provider interoperability is
assumed from mock tests. Device authorization remains outside this replacement.
