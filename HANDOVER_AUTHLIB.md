# Handover: Authlib integration for Cuiman

Date: 2026-09-09

## Current objective

The user's new objective is:

> Take full advantage of Authlib and use it how it is supposed to be used in
> applications like Cuiman.

Design around Authlib's intended OAuth client/session lifecycle. The aim is to
reduce the custom protocol and lifecycle code Cuiman owns and make the result
easier to understand. Adding Authlib underneath an otherwise unchanged Cuiman
token manager did not meet this objective.

This handover is the only work requested at this point. Do not resume
implementation automatically when reading it.

## Collaboration requirement: review between steps

The user explicitly clarified that **step-by-step means frequent review
breakpoints**. Previously, the agent moved from HTTPX2 migration through
protocol integration into expiry/concurrency implementation without stopping.
The user interrupted that work and subsequently requested its removal.

For continuation, propose one small next step, complete only that agreed step,
report its evidence and limitations, and pause for review. Do not interpret
approval of the overall objective as approval to execute all stages in one run.
The next substantive step should be architecture research and a concrete design
proposal, before modifying production code.

## Verified starting point

- Repository: `C:\Users\norma\Projects\eozilla`
- Branch: `forman/209-use_authlib`
- HEAD at handover: `ebab47941224dfc698a7e9f8b2e4ad513aa22918`
- The working tree contains the **HTTPX2-only checkpoint**. No commits were
  created during this work.
- Direct project dependencies and imports were migrated from `httpx` to
  `httpx2`, including authentication helpers, processing transport, app proxy,
  tests, and relevant documentation references.
- `api/transport/httpx.py` became `api/transport/httpx2.py`, and `HttpxTransport`
  became `Httpx2Transport`. Its test module was renamed correspondingly.
- The root and Cuiman dependency declarations now use `httpx2`. The root Pixi
  lockfile was regenerated; its only remaining diff is Cuiman's dependency name.
- Before adding this handover, the checkpoint diff contained 28 changed files,
  217 inserted lines and 217 removed lines, accounting for renames.
- **Authlib is not a declared dependency and no Authlib integration remains.**
  The experimental `auth/oauth_client.py` was removed from both the working tree
  and staging area. Added expiry fields, synchronization state, concurrency
  guards, and request preflight logic were also removed.

Validation of the restored checkpoint:

- `pixi run test-cuiman`: **611 passed, 4 warnings**, exit code 0.
- Warnings were the existing Typer deprecation and expected opener warnings.
- `git diff --check` passed.
- Full workspace tests, fresh coverage, formatting/checks, and documentation
  builds have not been run for this checkpoint.
- A pre-change saved coverage report showed 100% for the authentication,
  transport, and app modules. This is historical baseline evidence, not a fresh
  coverage result for the migration.

Git state has both staged and unstaged changes. The renamed transport source
and test files are staged additions; their old paths are unstaged deletions.
Preserve or deliberately reconcile that state without broad resets.

Unrelated pre-existing untracked paths:

- `eozilla-app/` — a separate nested checkout.
- `notebooks/s2gos-auth.ipynb`.

Do not overwrite, delete, stage, or read notebook secrets as part of this work.

## HTTPX2 dependency limits

The tested Pixi environment contained HTTPX2 2.5.0 and Starlette 1.3.1. Its
Starlette test client selects HTTPX2 when available.

HTTPX still appears transitively in the root lockfile through the locked
`anaconda-auth`, `dnspython`, FastAPI packages, and JupyterLab. The separate
`eozilla-airflow/pixi.lock` also contains upstream HTTPX requirements. No direct
project HTTPX imports were found in that Airflow workspace.

The checkpoint removes direct project usage; it does not claim that HTTPX is
absent from every environment. Dependency upgrades or packaging alternatives
need their own assessment. Do not delete required lockfile entries manually or
upgrade unrelated packages indiscriminately.

## Why the first Authlib attempt was rejected

The discarded implementation created temporary Authlib clients for individual
token operations while leaving Cuiman in charge of almost all lifecycle
decisions. It then added custom expiry checks, locks, generation counters,
configuration metadata, and request preparation.

Measured before reverting:

- Production code grew by 156 lines; authentication accounted for 133 of them.
- Tests shrank by 88 lines.
- 636 tests passed, but dedicated tests for new expiry/concurrency behavior had
  not yet been added. Passing tests did not establish architectural improvement.

Problems identified in review:

- A new adapter layer was added without replacing the existing token manager.
- Responses were validated before Authlib parsed them, then converted and
  validated again.
- Runtime locks were put inside Pydantic configuration models, requiring special
  equality/deep-copy behavior.
- Renewal coordination became spread across configuration, session helpers,
  transport, and app proxy.
- New features were mixed into the protocol migration, obscuring whether the
  library itself reduced complexity.

Do not reconstruct this implementation. Line count is supporting evidence, not
the sole acceptance criterion; ownership and comprehensibility matter more.

## Existing behavior and code to understand

Start with `AGENTS.md` and `docs/cuiman/authentication.md`. The latter accurately
describes the restored implementation, but its future-integration section is
context, not a mandate to preserve today's internal architecture.

Key implementation files under `cuiman/src/cuiman/`:

- `api/auth/config.py`: public settings, credentials, header rendering, and a
  persistence hook.
- `api/auth/session.py`: acquisition, renewal, fresh-login recovery, and
  persistence-before-publication rules.
- `api/auth/interactive.py`: prompts, browser login, callback waiting, and
  asynchronous cancellation.
- `api/auth/secret_store.py`: keyring profiles, large-token chunking, and storage
  error handling.
- `api/auth/oauth2.py`, `oauth2_async.py`, `oidc.py`, `oidc_async.py`: current
  custom protocol implementation.
- `api/auth/tokens.py`: the existing public `TokenResult` model.
- `api/client_mixin.py`, `api/async_client_mixin.py`: explicit login and lazy
  transport creation.
- `api/transport/httpx2.py`: API requests and a single retry after HTTP 401.
- `app/launch.py`: server-side credentials, launch exchange, and processing proxy.
- `api/config.py`, `cli/config.py`: configuration precedence and CLI workflows.

Tests worth reviewing include `tests/api/auth/`, `tests/api/test_client_login.py`,
`tests/api/test_config.py`, `tests/api/transport/test_httpx2.py`,
`tests/app/test_launch.py`, and `tests/cli/test_config.py`.

Existing user-facing behavior to account for in the proposal:

- Configuration files omit credentials; keyring records are scoped by canonical
  configuration path and API URL. Python/environment credentials are runtime
  overrides.
- Ordinary API requests never prompt or open a browser. Explicit login can;
  `force=True` bypasses existing tokens.
- Sync/async clients and app launch share authentication policy.
- OAuth2 password and client-credentials grants, OIDC public-client PKCE, static
  tokens, Basic, API keys, and proprietary login are supported.
- Password grants can recover once from a rejected refresh token when user
  credentials are available. Client-credentials grants ignore returned refresh
  tokens. OIDC refresh cannot start interactive login automatically.
- A persistence failure leaves live credentials unchanged. Remote token rotation
  cannot be undone by rolling back local state.
- There is currently no expiry metadata or coordinated concurrent renewal;
  only initial asynchronous login is coordinated.
- Browser callbacks, issuer validation, local secret storage, custom API headers,
  and injected-token notebook use remain application requirements to address.

Preserve externally useful behavior where practical, but do not retain every
helper or internal representation just to avoid discussing a design change.
Bring meaningful compatibility tradeoffs to the user's review before changing
the contract.

## Recommended next review step: Authlib ownership design

Research Authlib's actual supported application patterns and installed/versioned
source. Propose a design that answers:

1. Which Authlib integration fits a desktop/CLI/library client that also exposes
   a local FastAPI proxy? Assess HTTPX2 OAuth clients and framework integrations
   based on their intended session and browser context.
2. Who owns the authoritative OAuth token state? How do authenticated API
   requests use Authlib, its expiry handling, refresh, and update callback?
3. How are sync/async client lifetimes, closing, concurrency, and the app proxy
   handled without multiple independent token managers?
4. How does keyring persistence fit Authlib's update ordering? What happens if
   saving fails or a request is cancelled after the provider rotated a token?
5. Which Cuiman functions, classes, callbacks, and token conversions disappear?
   Show a concrete before/after ownership map and one ordinary request/refresh
   sequence. Avoid adding a provider registry or backend abstraction by default.
6. Which compatibility requirements need small adapters, and which would force
   substantial duplicate lifecycle code? Explain those tradeoffs honestly.

Research observations from the discarded attempt, to verify against the chosen
version:

- Authlib 1.8.0 was available on conda-forge and installed successfully during
  the experiment. It prefers HTTPX2 and deprecates its HTTPX fallback.
- Its HTTPX2 integration offers `OAuth2Client` and `AsyncOAuth2Client`.
- With a client secret, its default token-endpoint authentication is HTTP Basic;
  Cuiman currently sends credentials in the request body. Password grants without
  a client ID also need consideration.
- Authlib exposes expiry-aware requests and `update_token`. Source inspection
  showed token assignment before the persistence callback in refresh paths;
  simply attaching a keyring callback is insufficient evidence of the current
  failure guarantee.
- The asynchronous client has renewal locking, but that does not prove all
  explicit-refresh, cross-client, or sync/async scenarios are coordinated.

Primary references:

- https://docs.authlib.org/en/stable/oauth2/client/http/index.html
- https://docs.authlib.org/en/stable/oauth2/client/http/httpx.html
- https://raw.githubusercontent.com/authlib/authlib/v1.8.0/authlib/integrations/httpx_client/oauth2_client.py
- https://raw.githubusercontent.com/authlib/authlib/v1.8.0/authlib/oauth2/client.py
- https://raw.githubusercontent.com/authlib/authlib/v1.8.0/authlib/integrations/httpx_client/_compat.py

Deliver the design and pause. Do not silently proceed to dependency installation
or implementation. Device authorization and notebook token-provider callbacks
were previously deferred; the new objective calls for reassessing the design,
not automatically implementing every Authlib feature.

## Tooling and validation notes

Follow the repository's Pixi workflow. Add meaningful behavior tests and check
coverage for touched Cuiman code. Broader validation should eventually include
`pixi run tests`, `pixi run checks`, coverage, and `pixi run build-docs`.

The first sandboxed Pixi invocation failed while accessing its external cache
under `C:\Users\norma\AppData\Local\rattler\cache\uv-cache`. Running the same
command with approved elevated sandbox access worked. Some newly installed
Conda source files also required elevated read access because they were linked
to that cache. These were environment-access issues, not test failures.

No real Keycloak interoperability test was run. No user credentials or test
provider should be assumed available. No background work remains active.
