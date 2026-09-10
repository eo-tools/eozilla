# Authlib replacement: implementation plan

Date: 2026-09-10. Status: approved plan; slices 1 and 2 implemented; slice 2 ready for review.
Design: [AUTHLIB_DESIGN.md](AUTHLIB_DESIGN.md).

## Objectives

1. Less authentication code to maintain.
2. Easier configuration and authentication for users where possible.
3. One authentication interface and implementation used by the Python API, CLI,
   and launched app, with explicit ownership of the live HTTP client.

Backward compatibility is not a requirement. Preserve useful processing and
sign-in capabilities, not redundant fields, helper APIs, or historical recovery
policies. Keep familiar names when changing them would offer no benefit.

There are **three implementation slices**, with review after each. Tests,
documentation, and deletion belong to the slice that changes the behaviour;
they are not additional slices. No new research/proof phase is needed.

## 1. Replace the auth implementation and connect every consumer

Implemented, including the shared sync/async policy refactor requested during
implementation. Review evidence: [HANDOVER_AUTHLIB.md](HANDOVER_AUTHLIB.md).
Slice 1 was committed as `436188f`. Slice 2 is implemented below; slice 3 has not started.

**Outcome:** Python clients, CLI authentication, and the app proxy all use one
Authlib-based lifecycle. There is no remaining legacy OAuth engine.

- Use direct persistent Authlib HTTPX2 clients for client credentials, password,
  and OIDC authorization-code flows. Share configuration and storage policy across
  sync/async I/O. Do not retain the current password subclasses.
- Simplify OAuth2/OIDC configuration to provider settings and one complete
  `oauth_token` mapping. Keep static-token and API-key configuration distinct.
- Provide a small common client lifecycle: prepare/login, inspect token, logout
  where appropriate, and close. Introduce a client logout operation if that is the
  simplest way for Python and CLI to share revocation and local credential removal.
  Do not put another token manager behind this interface.
- Delegate grants, expiry, refresh, signing, PKCE/code exchange, and revocation
  to Authlib. Delegate OIDC signature/claims validation to Authlib and joserfc.
  Keep only local prompts/callback handling, discovery trust checks, and storage.
- Update every caller in the same slice: processing transport uses the owned
  requester; CLI uses client lifecycle methods; launched app borrows the owner's
  requester; standalone app owns a requester for its lifespan. Include the minimal
  sync-worker/async-owner-loop dispatch needed to make that ownership real.
- Apply the design's standard error behaviour: no automatic resource-401 replay,
  refresh-to-password fallback, or compatibility-only token-response normalization.
- Update the generator and regenerate clients if their generated structure changes.

**Delete here:** `auth/session.py`, one-shot OAuth helpers, handwritten OIDC
protocol operations and their async duplicates, OAuth `TokenResult` conversion,
config renewal factories, duplicate OAuth token fields and precedence rules,
password subclasses, transport/proxy renewal callbacks, browser-session token
headers, and per-proxy-request HTTP client creation. Remove obsolete exports and
update callers/tests directly; do not leave compatibility shims for later removal.

**Evidence:** tests through actual clients and mock HTTP for every supported auth
mechanism; OAuth acquisition/expiry/refresh; OIDC validation and callback rejection;
token persistence; initial CLI/API/app routing; ownership and close. Preserve
proxy security and processing-model tests. Run Cuiman tests/coverage and checks,
and update the affected documentation. Report the actual production-code delta.

This is deliberately the largest slice. An implementation that leaves CLI or app
using the old OAuth lifecycle has not completed it.

## 2. Simplify configuration and sign-in workflows

Implemented: one public-configuration prompt flow and profile loader; removal of
the legacy translator and bearer switch; saved-login reuse with explicit force
and no-input controls; safe CLI error reporting; ongoing refresh persistence
after explicit saving. See [HANDOVER_AUTHLIB.md](HANDOVER_AUTHLIB.md) for evidence.

**Outcome:** users configure a provider once and use the same credentials and
authentication concepts from Python, CLI, and the app.

- Make `configure` collect public provider settings without redundant token/grant
  inputs. Make `login` obtain and save credentials through the shared client,
  including client-credentials login. Make `logout` use the same revocation/local
  removal implementation available to Python callers.
- Consolidate credential prompts, configuration defaults, and actionable error
  messages. Keep explicit browser/prompt controls; ordinary API and proxy requests
  never start interaction. Avoid asking users to choose internal mechanisms.
- Remove redundant CLI options and overlapping public auth helpers. Retain useful
  Client and CLI workflows; explain any changed configuration or call examples.
- Make optional saving versus explicitly requested durable saving clear: optional
  storage failure warns without invalidating the live token; CLI login must not
  report successful saving when storage failed. Reuse the existing keyring module.
- Document the clean schema cut, including when a user must log in again. Do not
  add old-format migration machinery or aliases merely to preserve compatibility.

**Delete here:** remaining duplicated prompt/configuration orchestration, redundant
CLI flags and public conveniences identified during the workflow pass. No OAuth
protocol or recovery implementation should remain to migrate in this slice.

**Evidence:** Python and CLI scenarios for fresh setup, saved credentials, explicit
login, headless/browser login, storage failure, and logout, using fake HTTP/keyring.
Verify configuration/credential isolation and that errors never disclose secrets.
Run relevant tests and checks; update user examples alongside the changes.

## 3. Verify shared-session behaviour and complete the cut

**Outcome:** one authenticated session works predictably across processing calls
and the app, and the code reduction is demonstrated rather than assumed.

- Exercise Python and app requests against the same runtime across expiry and
  refresh rotation, including multiple browser sessions and overlapping calls.
- Verify sync worker dispatch and async owner-loop use, cancellation, app stop,
  owner close, and standalone server shutdown. Add only synchronization and cleanup
  demonstrated necessary by these tests; do not build a general lifecycle framework.
- Verify the user journey from configure/login through Python/app processing to
  logout. Retain launch-capability, cookie, origin, path, and header-filtering tests.
- Search for unused auth code, dead exports, stale documentation, and tests that
  only freeze removed implementation details. Remove leftovers and confirm no
  alternate OAuth lifecycle or live token copy has survived.
- Run `pixi run tests`, `pixi run checks`, Cuiman coverage, and `pixi run build-docs`.
  Check generator reproducibility if generated structure changed. Report real
  provider verification separately; an unavailable provider does not turn mock
  tests into interoperability evidence.

**Acceptance:** one shared auth implementation across CLI/API/app; one live OAuth
token authority per owner; simpler user configuration; and an actual net reduction
in production auth-related code. Show results against both `41181d3` (current
password slice) and `6dd44f4` (before that slice), using the same counting method.
Include auth code in config, client mixins, CLI, and proxy, wherever it resides.
Count tests and documentation separately. Moving code to wrappers or deleting
security checks does not satisfy the objective.

## Review reports

At each checkpoint, show what users can now do, what changed visibly, what code
was removed, and the test evidence and limitations. Slice 1 must already remove
the competing lifecycle; slice 3 is not a deferred compatibility-cleanup phase.
Do not add a fourth slice unless the user chooses to revise this plan.
