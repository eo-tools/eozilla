# Handover: Authlib integration for Cuiman

Updated: 2026-09-10. Status: client credentials and the shared mixin refactor are
committed. The authorized password-grant production slice is implemented in the
working tree and awaits user review.

## Resume here

The objective is to use Authlib's intended persistent OAuth client lifecycle to
reduce Cuiman's custom protocol and token-management code. The migration is
partially complete: OIDC, CLI login, and the launched-app proxy still use the
older implementation.

The user requires **small steps with review between them**. On this machine the
user authorized the bounded password-grant slice, including sync/async login,
refresh, fallback, one-401 recovery, snapshots, tests, and documentation. Review
that working-tree change before starting another migration step. Research,
design, and the isolated proof are already complete; approval of the objective
does not authorize all later work.

## Password-grant slice awaiting review

- `api/auth/client_credentials.py` has become
  [oauth2_client.py](cuiman/src/cuiman/api/auth/oauth2_client.py). Factories,
  persistence, response validation, and custom headers are shared by both grants.
  Two small password subclasses delegate protocol, expiry, rotation, and signing
  to Authlib while adding explicit login and password fallback.
- Password login accepts access-token or refresh-only bootstrap credentials.
  Missing credentials can prompt only during explicit login. Failed fresh login
  keeps the previous live token and does not publish prompted credentials.
- Automatic refresh retains omitted/empty/null refresh tokens. Forced login and
  fallback fetch replace the complete token. Only HTTP 400 `invalid_grant` from
  refresh permits password fallback; other errors do not. Missing refresh tokens
  permit password reacquisition at known expiry or after a resource 401.
- Password grants now use `client.token` and full keyring snapshots with absolute
  expiry, plus the existing warning-and-continue policy for expected save failures.
- Legacy sessions consume saved bootstrap snapshots once into their own token
  fields and discard stale snapshot metadata. CLI login and proxy ownership
  remain legacy; no old public helper has been removed. The mixins no longer use
  legacy header/session renewal for either OAuth2 grant.
- Failed initial refresh can be retried by the next API call even when the
  runtime still contains only a refresh token. No generator changes were needed.
- Regression evidence is
  [test_password_client.py](cuiman/tests/api/auth/test_password_client.py), using
  actual generated clients, real Authlib behavior, mock HTTP, a fake clock, and
  fake persistence. Existing login/transport assertions were updated for runtime
  ownership; legacy OIDC/session persistence tests remain.
- Baseline: 660 Cuiman tests, 29 subtests, 100% statement coverage. After this
  slice: **744 Cuiman tests, 29 subtests, 100% statement coverage**, with the same
  four warnings, on Python 3.14.6 / Authlib 1.8.0 / HTTPX2 2.5.0.
- `pixi run tests` passed across the workspace: 1,235 passed and four skipped.
  `pixi run checks` passed, including mypy over 118 source files. The docs build
  passed with notebook HTML, link, cross-reference, and theme warnings.
  `git diff --check` passed. No real provider or keyring was used in tests.
- Cancellation before an initial password response is tested. Broader transition
  coordination, cancellation during persistence, proxy sharing, and real provider
  verification remain deferred. Async password reacquisition without a refresh
  token is established for sequential use only.

## Repository checkpoint

- Branch: `forman/209-use_authlib`.
- HEAD on resume: `6dd44f4` (the previous handover update).
- No network fetch, commit, or push was performed for this slice.
- Relevant preceding commits:
  - `a125536e`: shared ClientMixin / AsyncClientMixin refactor.
  - `e771089e`: production Authlib client-credentials integration.
  - `84267657`: isolated lifecycle proof and persistence policy.
  - `2030a1ec`: design output.
- Before this slice, tracked files were clean. The only untracked path was
  `eozilla-app/`, a separate nested Git checkout. Preserve it.
- The password slice, tests, documentation, and this handover are uncommitted.
  Recheck Git state on resume.

The original workspace was `C:\Users\Norman\Projects\eozilla`. Resolve paths
below relative to the checkout on the other computer. Follow [AGENTS.md](AGENTS.md)
and the Pixi workflow. Local keyring credentials and environment overrides do not
travel with Git; tests use fake credentials. Keyring profiles are scoped to
canonical config path and API URL. Do not read or copy notebook secrets as part
of resuming this task.

## Decisions already settled

- A persistent Authlib HTTPX2 client owns the live OAuth token and signs resource
  requests. Configuration supplies bootstrap credentials and storage settings.
- The user explicitly does **not** require the old save-before-publication
  guarantee. Successful authentication remains usable when optional saving fails.
- Expected storage failures warn during ordinary requests and Python login;
  they do not roll back the live token or require another provider exchange.
  Explicit operations promising durable storage must still report save failure.
  Production CLI client-credentials login has not been added.
- Direct Authlib clients and callbacks suffice for the completed slice.
  Subclasses are a possible later tool, not a requirement.
- Runtime state stays outside Pydantic configuration. Avoid another token model,
  expiry algorithm, or parallel token manager around Authlib.
- `Client` and `AsyncClient` are generated by
  [tools/gen_client.py](tools/gen_client.py). Structural changes belong in the
  generator followed by regeneration, never manual edits to generated source.

An earlier attempt was rejected because it put temporary Authlib clients under
Cuiman's existing token manager and added lifecycle machinery. The accepted
direction replaces ownership, with code deletion as old paths are migrated.
The partial migration still retains legacy code needed by other callers.

## Implemented state

The default Pixi environment pins Authlib **1.8.0**; Cuiman declares
`authlib >=1.8,<1.9`. Tested HTTPX2 version: **2.5.0**. Root dependency changes and
the generated lockfile are committed. HTTPX remains transitively; removing
unrelated dependencies is outside this migration.

### Client credentials and persistence

[api/auth/oauth2_client.py](cuiman/src/cuiman/api/auth/oauth2_client.py)
constructs persistent `OAuth2Client` / `AsyncOAuth2Client` instances, configured
with client-secret POST authentication, the token endpoint, and grant metadata.
Authlib handles expiry, reacquisition, token normalization, and request signing.

Cuiman supplies small response/header adapters: preserve typed OAuth errors,
reject invalid token responses, discard refresh tokens returned for client
credentials, and support the configured custom access-token header. The shared
`needs_token()` helper checks credentials for initial/forced acquisition; it does
not calculate expiry.

Initial and forced login fetch on the same runtime. Explicit `fetch_token` does
not invoke Authlib's update callback, so login saves afterward. Automatic expiry
reacquisition uses the callback. Python `login()` can retry saving an existing
token without another grant. Ordinary API calls never prompt or open a browser.

- `client.token` returns a deep-copied live snapshot without initiating login.
  For authentication paths not migrated yet, it returns `None`.
- Client-credentials `client.config.auth` token fields remain bootstrap inputs,
  not a live token interface. Explicit access-token overrides discard stored
  OAuth metadata.
- `OAuth2AuthConfig.oauth_token` accepts a mapping or JSON object string, currently
  for password and client-credentials grants. Keyring stores the full snapshot as an
  `oauth_token` JSON string in its existing string-valued record. Absolute
  `expires_at` survives restore; the old duration is not restarted.
- Legacy access-only inputs remain usable and rely on resource-401 recovery when
  expiry is unknown. Public config files and notebook representations omit
  secrets, including the snapshot.
- `save_token()` persists a copied candidate config through the existing hook.
  It catches `SecretStoreError` and emits `CredentialStorageWarning`; unexpected
  errors propagate. There is no token rollback or background save queue.

### Shared mixins, transport, and close

[ClientMixinBase](cuiman/src/cuiman/api/client_mixin_base.py) centralizes runtime
initialization, token snapshots, the abstract config property, and common
transport construction. It is generic over the sync/async Authlib client type.

[ClientMixin](cuiman/src/cuiman/api/client_mixin.py) and
[AsyncClientMixin](cuiman/src/cuiman/api/async_client_mixin.py) retain explicit I/O,
login, and close methods. The async mixin initializes its login lock and rechecks
transport creation after awaiting login. This refactor required no generator
changes because the existing mixin hooks remain intact.

The earlier production change updated the generator to call
`_init_client_runtime()` and moved `close()` into the handwritten mixins. Both
clients were regenerated. Close releases the OAuth runtime even after login
alone, is idempotent, and closes it if an injected transport's close raises.

[Httpx2Transport](cuiman/src/cuiman/api/transport/httpx2.py) borrows the persistent
Authlib client; the Python client owns closing it. Model conversion and API error
mapping stay in the transport. The existing maximum one resource-401 renewal and
replay remains, using forced acquisition on the same runtime. Explicit request
auth/header overrides bypass managed authentication and its recovery.

## Evidence and limits

Production validation on Windows, using Python **3.14.6**:

- After the mixin refactor: **660 Cuiman tests passed**, 29 subtests, four existing
  warnings; **100% statement coverage across Cuiman**, including the new base.
- After the refactor: `pixi run checks` passed, including mypy over 118 source
  files. `git diff --check` passed.
- Before the refactor, the production slice also passed `pixi run tests` across
  the workspace and `pixi run build-docs`. The docs build emitted link,
  cross-reference, and notebook HTML warnings. These broader commands were not
  repeated after the refactor.
- Generator reproducibility was checked during the production slice: both files
  matched on a second run after ignoring generated timestamps.
- The subsequent `560e1c4a` commit only reformatted `_repr_json_`; tests were not
  rerun specifically for that formatting commit or this handover edit.
- No real provider/Keycloak interoperability or real keyring outage test was run.

Primary regression evidence is
[test_client_credentials.py](cuiman/tests/api/auth/test_client_credentials.py):
actual generated clients, real Authlib protocol/signing behavior, HTTPX2
`MockTransport`, a fake clock, and mocked persistence. It covers sync/async,
initial and forced login, expiry, saved metadata, warning/retry behavior,
malformed responses, custom headers, overrides, one-401 recovery, and close.
Existing login, transport, configuration, app, and CLI tests remain relevant.

The separate [proof](tools/authlib_proof/README.md) passed ten sequential sync/async
scenarios using Authlib 1.8.0, HTTPX2 2.5.0, and Python 3.12. It includes password
refresh rotation, but is a disposable experiment, not production integration.

Remaining limits:

- Keyring saving is synchronous even in async callbacks; a slow save can block
  the event loop. Worker-backed persistence and cancellation ownership/shielding
  are deferred.
- Authlib coordinates automatic async expiry renewal; Cuiman retains its initial
  async login lock. Broader coordination between explicit login, 401 recovery,
  expiry, threads, and independent clients is not implemented or proven.
- The app proxy still uses the legacy config/header path. It does not borrow the
  Python owner's Authlib runtime. Shared ownership across threads/event loops
  and shutdown needs a separately reviewed step.
- OIDC and public one-shot OAuth helpers still use their existing
  protocol/session code and persistence behavior. Do not apply client-credentials
  claims to those paths. CLI client-credentials login remains unsupported.
- Arbitrary non-rewindable request bodies and broader concurrency/cancellation
  behavior are not established by the sequential JSON request tests.

## Next review step

Review the password-grant working-tree slice and its compatibility boundaries.
After review, agree on one next step, such as transition coordination and
cancellation tests, before starting further implementation.

Keep transition coordination/cancellation, OIDC (including ID-token validation
compatibility), shared proxy ownership, and public helper deprecations as later
review checkpoints. Device authorization and notebook token-provider callbacks
remain deferred. No subsequent production slice is authorized yet.

## Reading and reproduction

Start with [authentication.md](docs/cuiman/authentication.md) for current
client-credentials versus legacy behavior. For storage/loading changes, inspect
`api/auth/config.py`, `api/auth/secret_store.py`, and `api/config.py`; for the
remaining legacy paths, inspect `api/auth/session.py`, `oauth2.py`, and `oauth2_async.py`.
These implementation paths are under `cuiman/src/cuiman/`.

[AUTHLIB_DESIGN.md](AUTHLIB_DESIGN.md) and
[AUTHLIB_RESEARCH.md](AUTHLIB_RESEARCH.md) retain design rationale and versioned
primary-source references. They are historical documents: statements that
Authlib is not installed or production integration has not started are stale.
This handover and current source take precedence for implementation status.
Proposed subclasses and transition gates in the design are not completed code.

From the checkout root, restore the locked environment with `pixi install`.
To reproduce the production coverage result:

```console
pixi run pytest cuiman/tests --cov=cuiman/src/cuiman --cov-report=term-missing -q
pixi run checks
```

Use `pixi run test-cuiman` for an ordinary package run. Run broader workspace
tests/docs as appropriate to the next change. The proof has its own manifest and
reproduction commands in its README.

On the original machine, sandboxed Pixi calls sometimes could not read packages
linked to its external cache; approved elevated execution succeeded. Treat those
as environment access failures, not evidence of missing dependencies or failing
tests. For generator runs on Windows, `$env:PYTHONUTF8='1'` avoids console encoding
errors from Unicode checkmarks. There is no background work to resume.
