# Handover: Authlib replacement for Cuiman

Updated: 2026-09-10. Slice 1 is implemented and ready for review. Stop at this
checkpoint; slices 2 and 3 in [AUTHLIB_PLAN.md](AUTHLIB_PLAN.md) have not started.
The working tree contains the implementation; it has not been committed here.

## Direction and current structure

The user wants less authentication code to maintain, easier use, and the same
authentication interface across Python, CLI, and the app. Backward compatibility
is not required. The rejected password implementation at `41181d3` has been
replaced following [AUTHLIB_DESIGN.md](AUTHLIB_DESIGN.md). `6dd44f4` is the earlier
comparison point, before that password slice.

Each Cuiman client owns a direct persistent Authlib `OAuth2Client` or
`AsyncOAuth2Client` for OAuth2/OIDC, or an HTTPX2 client for other authentication.
Authlib owns grants, expiry, refresh, signing, PKCE, code exchange, and revocation.
OIDC signature and claims checks use joserfc and Authlib. Cuiman retains local
interaction, discovery trust checks, OS-keyring storage, and app proxy security.

The user identified excessive duplication between the two client mixins during
implementation. Their common decisions now live in `client_mixin_base.py`:
credential selection, HTTP client setup, initial request preparation, discovery
acceptance, token validation policy, persistence, and transport/request options.
The mode-specific mixins execute sync/async I/O and handle locks, cancellation,
closure, and app dispatch. No OAuth subclasses, custom coroutine runner, or
replacement token manager were introduced to hide those I/O differences.

Processing transport calls the owner's requester. CLI login/logout call the
client lifecycle. A launched app borrows that requester; its browser sessions
contain opaque identifiers instead of upstream token snapshots. A standalone
app owns an AsyncClient and closes it through the server lifespan.

## User-visible changes

- Shared `login(interactive=True, no_browser=False, force=False, save=False)`,
  `token`, `logout()`, and `close()` operations; await the operations for AsyncClient.
  Ordinary processing and proxy requests never prompt or launch a browser.
- OAuth2 and OIDC accept one complete `oauth_token` bootstrap mapping. Separate
  OAuth access/refresh fields and custom bearer/header settings are removed.
  Both require a client ID. Static tokens and proprietary login retain their
  purpose-specific token/header fields. CLI client-credentials login is supported.
- Authlib refreshes known-expired tokens. Rejected refresh propagates the library
  error; processing-service 401 responses are not replayed. Fresh login is explicit.
- The runtime owns live OAuth tokens; `client.token` returns a copy. Configuration
  is not a live token view. OIDC snapshots retain `_cuiman_nonce` so refreshed
  ID-token nonces can be checked after restarting the client.
- Optional keyring updates warn on storage failure without invalidating live
  credentials. Explicit `login(save=True)` requires successful saving. CLI uses it.
  Loaded configurations retain their source profile when wrapped in a client,
  so explicit saving, refresh persistence, and logout target the same profile.
- Logout attempts OIDC revocation when advertised, then removes local secrets and
  closes, including when revocation fails. Closed clients cannot be reused.
- An asynchronous app owner must remain on its original running event loop.
  App shutdown does not close a borrowed client.

User documentation: [authentication](docs/cuiman/authentication.md),
[configuration](docs/cuiman/configuration.md), and [API](docs/cuiman/api.md).
Existing OAuth configurations need obsolete fields removed and another login;
there is no compatibility alias layer.

## Deletions

Removed `auth/session.py`, `oauth2.py`, `oauth2_async.py`, `oidc_async.py`,
`login_async.py`, and `tokens.py`; removed password subclasses, one-shot OAuth
exports, configuration renewal factories, token reconciliation, resource-401
recovery, transport/proxy renewal callbacks, per-browser token headers, and
per-proxy-request HTTP client construction. Proprietary response parsing remains
small and separate. Replaced tests of the deleted helper graph with tests through
actual Authlib clients and mock HTTP; retained processing, keyring, callback, and
proxy security coverage.

## Verification

- `pixi run tests`: 959 passed, 4 skipped across all six workspace packages.
  Package counts: Appligator 161, Cuiman 468, Eozilla 1, Gavicore 70,
  Procodile 153, Wraptile 106 passed and 4 skipped.
- Cuiman production statement coverage: 100%, 2,738 statements. The dedicated
  coverage run also reports 25 passing subtests. Existing Typer/opener warnings
  remain; the workspace run also reports existing Procodile warnings.
- `pixi run checks`: passed, including mypy for 112 source files.
- `pixi run build-docs`: passed, with existing notebook HTML, link, and
  cross-reference warnings.
- Client regeneration is reproducible except for generated timestamps.
  The generator now shares the synchronous lazy transport setup; resource I/O
  remains sync/async. Generated files were regenerated, not edited independently.
- `git diff --check HEAD`: passed.

Tests exercise initial grants, expiry and rotation, native errors/no replay,
OIDC signed ID tokens and rejection, callback state/duplicate parameters,
optional and required saving, source profiles, CLI flows, shared API/app refresh,
multiple browser sessions, cancellation, owner loops, and lifespan closure.
No real provider login or OS-keyring interoperability was performed; fake HTTP
and storage provide behavioral evidence, not real-provider verification.

## Code size

The production comparison includes **all Python files under `cuiman/src` plus
`tools/gen_client.py`**, including configuration, CLI, proxy, and generated clients.
It therefore includes additions outside the auth directory. The same counting
method is used for both committed baselines and the working tree.

| Scope / measure | `6dd44f4` | `41181d3` | Working tree |
| --- | ---: | ---: | ---: |
| Production physical lines | 7,863 | 8,082 | 7,344 |
| Production nonblank, non-comment lines | 6,282 | 6,462 | 5,900 |
| Cuiman test Python physical lines | 9,911 | 10,419 | 7,762 |
| Cuiman user-documentation Markdown lines | 1,434 | 1,464 | 1,378 |

Production reduction: **738 physical lines** against the password checkpoint,
and **519** against the earlier checkpoint. Excluding blanks/comment-only lines,
the reductions are 562 and 382. Tests and documentation are counted separately;
root planning/handover documents are outside these implementation totals.

## Remaining work after review

Slice 2 consolidates configuration/sign-in workflows and removes remaining
redundant CLI options and prompt orchestration. Slice 3 completes broader
concurrency, cancellation, rotation, and configure-to-app end-to-end verification.
Both current client modes serialize requests on one owner; any relaxation needs
behavioral tests, rather than another lifecycle framework. Keep the existing
three slices and review checkpoints. Do not reopen the old compatibility design
or add another research/proof phase. The nested `eozilla-app/` checkout was not
modified by this slice.
