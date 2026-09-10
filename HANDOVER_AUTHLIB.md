# Handover: Authlib replacement for Cuiman

Updated: 2026-09-10. **Slice 2 is implemented and ready for review.** Slice 1
was committed by the user as `436188f`. Slice 2 remains uncommitted. Stop at this
checkpoint; slice 3 in [AUTHLIB_PLAN.md](AUTHLIB_PLAN.md) has not started.

## Direction

The user wants less authentication code to maintain, easier use, and one auth
interface across Python, CLI, and the app. Backward compatibility is not required.
The rejected password implementation at `41181d3` was replaced in slice 1;
`6dd44f4` is the earlier comparison point. [AUTHLIB_DESIGN.md](AUTHLIB_DESIGN.md)
is the current design. Keep the three agreed slices and their review checkpoints.

Each client owns a direct persistent Authlib OAuth2Client/AsyncOAuth2Client, or
HTTPX2 for non-OAuth auth. The existing ClientMixinBase shares local decisions;
mode-specific mixins handle I/O, locks, cancellation, closure, and app dispatch.
Processing transport and the launched app borrow the owner's requester. A
standalone app owns an AsyncClient for its server lifespan. Authlib owns grants,
expiry, refresh, signing, PKCE, code exchange, and revocation; Authlib/joserfc
validate OIDC tokens. There is no Cuiman OAuth subclass or replacement token manager.

## Slice 2 changes

- Replaced the CLI's context model and many prompt helpers with one public-settings
  prompt flow. It reuses current public defaults, normalizes auth/grant choices,
  and rejects supplied settings that do not apply to the selected auth type.
  Changing auth type does not inherit unrelated provider settings.
- Removed the legacy configuration translator. `configure` warns and starts from
  defaults for an incompatible file, then writes only validated public settings.
  Old values are not translated, displayed, or silently retained. File loading
  continues rejecting secret-bearing configurations. Users provide settings again
  and log in; aborted/invalid configuration does not overwrite the previous file.
- Static `token` and proprietary `login` now use one optional
  `access_token_header`: omitted/None means Bearer; a header name sends the raw
  token in that header. Removed `use_bearer` and `configure --use-bearer`.
  Existing Bearer profiles must remove both the old switch and unused default
  `X-Auth-Token` field. API keys retain their header and gain `--api-key-header`.
- One profile loader supports processing, login, and logout. Deleted the separate
  login-config loader and duplicate missing-file/credential checks.
- Default login reuses available credentials and prompts only for missing fields.
  Interactive `force=True` prompts for replacements (or starts OIDC sign-in).
  `force=True, interactive=False` uses supplied credentials for a fresh grant.
  CLI `--force`, `--no-input`, and `--no-browser` map to these shared operations;
  scripts can use `login --force --no-input`. No processing/proxy request interacts.
- CLI login, logout, and offered login share error handling. Provider OAuth/JWT/HTTP
  failures produce an actionable message without echoing raw token responses.
  Processing commands report native OAuth/JWT auth failures through the same
  handler unless traceback output was explicitly requested. Configuration
  validation messages omit input values. Python library errors remain native.
- Successful `login(save=True)` now registers the profile for subsequent optional
  refresh saves, including Python/environment credentials. Explicit save failures
  still raise; optional refresh-save failures warn and retain the live token.
  Named-profile identity remains shared by save, refresh, and logout.

User-facing details: [authentication](docs/cuiman/authentication.md),
[configuration](docs/cuiman/configuration.md), [API](docs/cuiman/api.md), and the
regenerated [CLI reference](docs/cuiman/cli.md).

## Verification

- Cuiman: **488 passed**, 23 passing subtests, 4 existing warnings; **100% production
  statement coverage**, 2,672 statements.
- `pixi run checks`: passed, including mypy for 112 source files.
- `pixi run gen-cli-docs` and `pixi run build-docs`: passed. The docs build still
  reports existing notebook HTML, link, and cross-reference warnings. Other CLI
  reference files were regenerated without producing changes.
- `pixi run tests`: **979 passed, 4 skipped** across all six workspace packages.
  Existing Typer/opener/Procodile warnings remain.
- `git diff --check`: passed.

Tests cover all public provider prompts, current/default/branded configuration,
clean recreation of incompatible files, rejected irrelevant options, partial
credentials, saved login reuse, forced sync/async login, noninteractive CLI login,
provider-error privacy, revocation-failure cleanup, and continued token rotation
persistence after explicit saving. Existing processing, keyring, OIDC validation,
callback, proxy security, owner-loop, cancellation, and lifespan tests remain.
No real provider or OS-keyring interoperability was performed; fake HTTP/storage
provide behavioral evidence only.

## Code size

Production counts include **all Python files under `cuiman/src` plus
`tools/gen_client.py`**, including configuration, CLI, proxy, and generated clients.
Tests and documentation are counted separately. Root planning/handover documents
are excluded. The same method applies to all baselines.

| Scope / measure | `6dd44f4` | `41181d3` | Slice 1 `436188f` | Slice 2 |
| --- | ---: | ---: | ---: | ---: |
| Production physical lines | 7,863 | 8,082 | 7,344 | 7,224 |
| Production nonblank, non-comment lines | 6,282 | 6,462 | 5,900 | 5,810 |
| Cuiman test Python physical lines | 9,911 | 10,419 | 7,762 | 7,820 |
| Cuiman user-documentation Markdown lines | 1,434 | 1,464 | 1,378 | 1,413 |

Slice 2 removes **120 additional production lines** (90 excluding blanks/comment
lines). Total reduction is 858 physical lines against the password checkpoint,
or 639 against the pre-password checkpoint. No auth implementation was moved to
another package or a generated helper to obtain these reductions.

## Remaining slice 3

Complete broader overlapping-request, cancellation, refresh-rotation, and
configure-to-app end-to-end verification; audit remaining dead code and docs;
confirm the final code reduction. Both client modes currently serialize requests
on one owner. Relax this only with behavioral evidence, without adding another
lifecycle framework. The async owner's event loop must outlive the launched app.
Keep the existing issuer/state and proxy security checks. Device authorization
and speculative provider adapters remain outside this replacement.

The nested `eozilla-app/` checkout was not modified. No temporary dotted scripts
or logs were added to the repository root during slice 2.
