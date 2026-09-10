# Handover: completed Authlib replacement for Cuiman

Updated: 2026-09-10. **All three implementation slices are complete.** Slice 1
was committed as `436188f`, slice 2 as `f1d8cc8`; the final slice is uncommitted.
[AUTHLIB_PLAN.md](AUTHLIB_PLAN.md) and [AUTHLIB_DESIGN.md](AUTHLIB_DESIGN.md) record
the completed plan and design. Final workspace verification is recorded below.

## Result

The user wanted less auth code to maintain, easier use, and the same auth
interface across Python, CLI, and the app, without backward-compatibility constraints.

Each client owns a direct persistent Authlib OAuth2Client/AsyncOAuth2Client, or
HTTPX2 for non-OAuth authentication. Authlib owns grants, expiry, refresh, signing,
PKCE, code exchange, and revocation. Authlib/joserfc validate OIDC signatures and
claims. Cuiman retains local prompts/callbacks, discovery trust checks, keyring
storage, and app-proxy security. There are no Cuiman OAuth subclasses or competing
token manager. ClientMixinBase shares local policy; the two mixins execute their
I/O and manage locks, cancellation, closure, and app dispatch.

The processing transport calls the owner's requester. CLI login/logout use the
client lifecycle. A launched app borrows that same requester and keeps only opaque
browser-session identifiers. A standalone app owns an AsyncClient for its lifespan.

## Interface and configuration

- `login(interactive=True, no_browser=False, force=False, save=False)`, `token`,
  `logout()`, and `close()` are shared across client modes; await async operations.
  Ordinary processing/proxy requests never prompt or open a browser.
- Login reuses available credentials and prompts only for missing fields.
  Interactive forced login prompts for replacements or starts OIDC authorization;
  forced noninteractive login uses supplied credentials for a fresh grant.
  CLI `--force`, `--no-input`, and `--no-browser` use the same controls.
- OAuth2/OIDC use one complete `oauth_token` bootstrap mapping and require a client
  ID. Authlib owns the live token; `client.token` returns a copy. OIDC snapshots
  retain `_cuiman_nonce` for refresh validation after restart.
- Static token/proprietary login use one optional `access_token_header`: omitted
  means Bearer; a name sends the raw token in that header. `use_bearer` and its CLI
  switch are removed. API keys retain their own header setting.
- Configure uses one prompt flow, reuses current public defaults, and rejects
  irrelevant options. Incompatible files are recreated from defaults without
  translating old settings. Files contain no credentials; users sign in again.
- Explicit saving must succeed and enables later refresh updates to that profile.
  Optional storage failure warns without discarding live credentials. Loaded
  profiles retain their identity for save, refresh, and logout.
- No resource-401 replay or refresh-to-password fallback. Provider failures in
  the CLI get an actionable message without raw token responses; Python receives
  native library errors. Logout revokes OIDC credentials when advertised, removes
  local credentials, and closes. Closed clients cannot be reused.

See [authentication](docs/cuiman/authentication.md),
[configuration](docs/cuiman/configuration.md), [API](docs/cuiman/api.md), and
[CLI reference](docs/cuiman/cli.md) for examples and configuration-cut details.

## Final ownership fix and evidence

A deterministic test demonstrated that cancelling logout while it waited for the
owner lock cleared credentials used by an active request. Logout cleanup now runs
inside the acquired lock in both modes. Async close has one private helper so
logout can close while holding that lock without reacquiring it. No new state,
lock type, background event-loop service, or lifecycle framework was introduced.

The final slice adds 24 scenarios covering:

- Overlapping first requests and refresh, plus two independent browser sessions
  overlapping an API request, use one live HTTP client and one grant per cycle.
- Cancelling queued login/close/logout leaves the active owner untouched.
  Cancelling an active HTTP operation releases the async lock; cancelling OIDC
  key validation discards the unverified token without saving or using it.
- Logout finishes local cleanup and closure before queued requests, including
  revocation cancellation/failure. Close waits for active requests.
- Cancellation from a foreign app loop reaches the async HTTP operation. A sync
  worker finishes its already-started request; owner close waits for it.
- Standalone server lifespan shutdown waits for an active refresh, then closes
  its owned client. Existing tests retain borrowed-owner shutdown behavior.
- Configure, CLI login, API processing, app processing, refresh rotation, and
  logout work for password, client credentials, and OIDC with both client modes.
  The workflow uses real keyring serialization with fake backend calls and checks
  isolation from another profile and another service URL. OIDC refresh validates
  a newly rotated signing key. Logout blocks later proxy/API use and requires login.

## Deletions and audit

The migration removed the legacy session engine, one-shot OAuth helpers and async
copies, password subclasses, TokenResult conversion, configuration renewal
factories, duplicate OAuth token fields, resource-401 recovery, proxy token/header
snapshots, and per-proxy-request client creation. Slice 2 removed the legacy
configuration translator and duplicated prompt/profile-loading orchestration.
The final audit found no remaining competing OAuth lifecycle in production.

The final slice also removes the superseded `tools/authlib_proof` script, README,
and Pixi manifests. Its 288-line proof and separate environment are no longer
needed alongside actual-client tests. This removal is separate from the production
reduction below; no implementation was moved into another package or helper.

## Verification

- Cuiman: **512 passed**, 23 passing subtests, 4 existing warnings;
  **100% production statement coverage**, 2,671 statements.
- `pixi run checks`: passed, including mypy for 112 source files.
- `pixi run build-docs`: passed, with existing notebook HTML, link, and
  cross-reference warnings.
- `pixi run tests`: **1,003 passed, 4 skipped** across the workspace.
  Per-package passes: Appligator 161, Cuiman 512, Eozilla 1, Gavicore 70,
  Procodile 153, Wraptile 106. Existing Typer/opener/Procodile warnings remain.
- `git diff --check`: passed. Client-generator reproducibility was verified in
  slice 1; slices 2/3 did not change generated structure. CLI docs were regenerated
  in slice 2 and are unchanged by the final slice.

## Code size

Production includes **all Python files under `cuiman/src` plus
`tools/gen_client.py`**, including config, CLI, proxy, and generated clients.
Tests and user documentation are counted separately. Root planning documents and
the retired standalone proof are outside the production total. Each committed
baseline and the final working tree use the same counting method.

| Scope / measure | `6dd44f4` | `41181d3` | Slice 1 `436188f` | Slice 2 `f1d8cc8` | Final |
| --- | ---: | ---: | ---: | ---: | ---: |
| Production physical lines | 7,863 | 8,082 | 7,344 | 7,223 | 7,224 |
| Production nonblank, non-comment lines | 6,282 | 6,462 | 5,900 | 5,810 | 5,810 |
| Cuiman test Python physical lines | 9,911 | 10,419 | 7,762 | 7,820 | 8,476 |
| Cuiman user-documentation Markdown lines | 1,434 | 1,464 | 1,378 | 1,413 | 1,436 |

Final production reduction: **858 physical lines** against the rejected password
checkpoint, or **639** against the pre-password checkpoint. Excluding blanks and
comment-only lines, the reductions are 652 and 472. The final correctness fix adds
one physical production line versus committed slice 2, with no increase in
nonblank, non-comment lines.

## Limits

Both modes serialize requests on one owner. The async owner's loop must outlive
the launched app. Cancelling a wait cannot undo a request already received by a
provider, and sync worker I/O may finish after the caller stops waiting. Lost
refresh responses can require explicit fresh login; no recovery engine was added.

All provider/keyring verification used fake HTTP or backend calls. No live-provider
or actual OS-keyring interoperability is claimed. Device authorization and
speculative provider adapters remain outside the requested replacement. The
nested `eozilla-app/` checkout was not modified. No temporary root dotfiles remain.
There is no remaining implementation slice in this plan.
