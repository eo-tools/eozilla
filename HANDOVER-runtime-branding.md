# Runtime branding and configuration handover

Updated 2026-10-15. The latest decisions below supersede the earlier scope
changes in this chat. The implementation does not yet match the final design.

## Resume here

Follow-up implementation on 2026-10-15: the user approved explicit local paths
and two dedicated asset endpoints (favicon and icon), replacing the generic
registry proposal below. Python now supports `AppImageIcon(path=...)` versus
`AppImageIcon(url=...)` for both images, plus `Path(...)` favicon shorthand.
Local bytes are snapshotted at server creation, served with session authentication
and no-store headers, and referenced by app-relative URLs in `config.json`.
Missing files warn and omit the corresponding branding override; other read
errors propagate. MIME types use filename extensions with an octet-stream
fallback. Saved profiles retain explicit `path` objects. Cuiman customization
documentation now describes this interface. At that checkpoint, browser runtime
configuration and the bundled rebuild remained separate review steps.
The historical session and Git-state notes below describe the previous handover.

Browser follow-up on 2026-10-15: after the user approved the Python checkpoint,
they authorized the browser implementation. Root HEAD was `f95d650e`; frontend
HEAD was `0613907`. That frontend checkout had none of the older branding code,
so branding was implemented against its current secure-launch entry point.
The browser now loads optional `config.json`, applies branding before React,
and supports standalone public `service` settings using the existing custom
provider and authentication form. Cuiman ignores `service` and uses Python's
branding with the existing proxy. No branding query overrides were introduced.
Runtime selections take precedence without replacing saved choices at startup;
matching saved credentials remain in the existing separate session store.
Vite/build-time branding and service-default environment settings were removed.
The standalone production build and strict documentation build passed.
The standard Node suite passed 245 tests (46 browser-only/existing skips),
and focused Chromium loader/header checks passed 41 tests. TypeScript and ESLint
passed. The full Chromium run exposes existing test-harness incompatibilities:
tests that replace native `window`, browser imports of Node's server renderer,
and a code-theme timing assertion. The new startup integration tests run in Node
with browser globals/wrappers stubbed; rendered header/DOM checks run in Chromium.
Bundled Cuiman rebuild and final Python/browser integration remain the next
review checkpoint; no commits or pushes were made in this browser follow-up.

Follow-up validation: `pixi run test-cuiman` passed 719 tests with 100% coverage
for `cuiman.api.branding`, `cuiman.api.config`, and `cuiman.app.launch`.
`pixi run checks` and `pixi run build-docs` passed. The docs build copies
`docs/hooks/download_fonts.py` into `site/hooks/`; remove that generated copy
before running checks to avoid mypy reporting a duplicate module.
No browser changes, bundled rebuild, commits, or pushes were made in this follow-up.

Work in `C:\Users\norma\Projects\eozilla`. Read `AGENTS.md` and:

- https://github.com/eo-tools/eozilla/issues/244
- https://github.com/eo-tools/eozilla-app/issues/101

The previous session ended with intermediate work for the user to commit.
The follow-up session explicitly authorized the Python asset implementation.
On resumption, inspect both checkouts and their current commits before editing.

The original sequence had at most four steps, with user review between them:

1. Design.
2. Cuiman implementation.
3. Browser implementation.
4. Documentation, bundled app rebuild, and integration verification.

Steps 2 and 3 have partial implementations and prior successful tests. The user
returned to design discussion on 2026-10-15. The revised design now requires
changes to both Python and the browser; do not treat the earlier steps as final
or proceed directly to step 4. Continue from this agreed design when the user
resumes implementation, retaining review checkpoints.

## Latest agreed design

### One optional configuration URL

- The browser loads `GET ./config.json`, relative to the browser-visible app URL,
  before React renders. The same URL supports both Cuiman and standalone apps.
- Cuiman first exchanges `?launch=<one-shot-code>` at `POST ./_cuiman/launch`.
  Keep its existing HTTP 204 response and HttpOnly session cookie. Do not return
  configuration from this POST; that alternative was discussed and rejected.
- Cuiman serves dynamic, session-authenticated `GET /config.json`. After URL
  cleanup, the `cuiman=1` marker and session cookie support reloads.
- Standalone deployments serve a static `config.json` beside `index.html`.
  Vite's `public/config.json` is a development/build convenience; a deployer
  may also add or replace the file in the deployed app without rebuilding.
- The endpoint/file is optional. HTTP 404 means absent configuration and uses
  defaults. Other HTTP/network errors and malformed configuration should show
  a clear startup error. A Cuiman authentication failure must not become an
  optional-file fallback. Keep authenticated responses uncached.

### Configuration shape and mode precedence

The JSON may contain `branding` and `service`. For example, standalone JSON:

```json
{
  "branding": {
    "title": "Sen4CAP",
    "favicon": "./assets/favicon.svg",
    "icon": {"url": "./assets/logo.svg"}
  },
  "service": {
    "apiUrl": "https://api.example.org/",
    "authType": "oauth2",
    "oauth2Protocol": "oidc",
    "authorizationServerUrl": "https://auth.example.org/",
    "clientId": "sen4cap-browser"
  }
}
```

- The name is `service`, not the earlier experimental `defaultService`.
- `service` contains public connection/authentication configuration only:
  API URL, auth type, issuer, public client ID, scopes, and applicable public
  endpoint/header settings. The user explicitly means non-credential settings.
- In standalone mode, an existing `service` entry configures the intended
  connection and takes precedence over a saved service selection. Without it,
  preserve the existing saved-selection/service-dialog behavior. Keep existing
  sign-in and credential handling rather than implementing a new auth flow.
- In Cuiman mode, ignore a `service` entry. The Python client owns all service
  configuration and credentials; the browser uses the existing Cuiman proxy.
- In Cuiman mode, all effective configuration comes from Python. Do not let a
  static deployment file or new branding query overrides supersede it.
- Branding merges field by field with built-in defaults. Defaults are title
  `Eozilla`, favicon `./eozilla-small.svg`, and header emoji `🦖`. Fields are
  optional and missing/null fields fall back. An icon has exactly one of
  `{"emoji":"🌍"}` or `{"url":"..."}`.
- Branding and public service configuration should require no custom app build.
  Replace frontend branding/service-default `.env` usage with runtime config
  and built-in defaults. Build metadata such as version/build number may remain.
- The user briefly proposed a separate standalone PR, then explicitly brought
  standalone runtime configuration back into scope: the shared `config.json`
  loader plus a standalone-only `service` entry provides it in one go.
- Preserve existing presentation/launch parameters. The final standalone query
  override contract has not been settled; do not assume the legacy `service`
  query parameter should be restored or introduce many new API/auth parameters.

### Python-served branding assets

A relative URL alone does not make a Python-local file available to the browser.
The user explicitly requires Cuiman callers to configure assets through Python,
without copying files into the frontend `public/` directory.

- Use only `GET /_cuiman/assets/favicon` and `GET /_cuiman/assets/icon`.
- Python snapshots explicitly supplied local favicon and header-image files.
- No generic asset-name registry or arbitrary filesystem-path endpoint is exposed.
- Use the existing Cuiman session authentication for asset requests.
- Python-generated `config.json` references the registered assets using relative
  browser URLs, for example:

```json
{
  "branding": {
    "title": "Sen4CAP",
    "favicon": "./_cuiman/assets/favicon",
    "icon": {"url": "./_cuiman/assets/icon"}
  }
}
```

- Resolve relative URLs against the browser-visible app URL, preserving Jupyter
  proxy prefixes. Leading `/` remains origin-relative; external HTTP(S) URLs
  remain supported.
- Use `AppImageIcon(path=...)` for local files and `AppImageIcon(url=...)`
  for browser URLs. Favicon also accepts `Path(...)` or a URL string.
  Exactly one image source is required. See the follow-up note above for
  missing-file behavior, MIME types, and snapshot lifetime.
- For standalone apps, the developer must statically deploy the referenced files,
  e.g. `index.html`, `config.json`, `assets/favicon.svg`, and `assets/logo.svg`.
  App-relative paths in JSON then work without a custom build. External HTTP(S)
  assets are also possible.

## Current implementation: Python

- `cuiman/src/cuiman/api/branding.py`: public Pydantic models `AppBranding`,
  `AppEmojiIcon`, `AppImageIcon`; strict nonempty strings, forbidden extra fields.
  Re-exported from `cuiman.app`.
- Branding belongs to `ClientConfig.branding`, not a separate `show_app()` or
  `serve()` argument. Profile/environment/settings precedence and snapshots
  support it. Partial branding merges preserve fields; icon overrides replace
  the whole icon. Empty branding is omitted from saved profiles.
- `AppBranding.from_file(path)` explicitly loads UTF-8 JSON with branding fields
  directly, e.g. `{"title":"Sen4CAP"}`, not the runtime JSON wrapper. It expands
  `~` and propagates file/validation errors. No file is loaded implicitly.
- `cuiman/src/cuiman/app/launch.py` snapshots branding and serves authenticated
  `GET /config.json`, returning only `{"branding": ...}` with no-store headers.
  The route precedes the static app mount. Launch response stays 204.
- Dedicated favicon/icon endpoints and local file snapshots are implemented.
  Existing asset strings still represent browser URLs.

## Current implementation: browser

The separate nested Git checkout is `eozilla-app/`.

- `src/config/bootstrap.ts` holds branding defaults, optional config loading,
  public service validation, and document title/favicon application. It requests
  JSON explicitly (avoiding Vite's HTML fallback), uses no-store, and treats only
  404 as absent. Invalid configuration and authentication failures show a startup
  error. Relative images resolve against the browser-visible app URL.
- `src/main.tsx` keeps the existing launch exchange, then loads branding before
  rendering. Branding passes through App to Header as an explicit prop.
- `index.html` has built-in title/favicon values. Header supports emoji/image
  objects. Branding and service-default `.env` values were removed; version/build
  metadata remains build-time configuration. No branding query overrides exist.
- Standalone `service` settings select a `configured` CustomServiceProvider and
  prefill its schema defaults. The existing sign-in flow remains unchanged.
  The existing transient-selection mechanism now supports runtime deployments,
  matching saved credentials, sign-in/sign-out, and clearing stale Cuiman state
  on standalone startup. Configuration JSON never accepts credential fields.
- The initial `runtime.ts`/`startup.ts` modules and their tests were removed from
  the working tree. Do not restore that general framework automatically. The
  user strongly prefers narrow changes and minimal changes to existing logic.
- Browser README and workspace app/provider docs describe the runtime contract.
  The bundled rebuild and final integration remain pending.

## Why the old service query parameter disappeared

This was traced during this session; do not repeat the incorrect assumption that
it is still supported:

- App commit `8eb51b86e0df7dacf71ebf38d18eff222ced2a79` (2026-09-02), authored and
  committed by Norman Fomferra: "Removed the legacy service query protocol completely".
- It followed the secure Cuiman launch implementation (`840bda6`) and was merged
  in https://github.com/eo-tools/eozilla-app/pull/82 (issue #80).
- Companion changes were merged in https://github.com/eo-tools/eozilla/pull/201
  (issue #198); root removal commit is `bc84b960`.
- Previously `?service=...` carried base64url JSON with `id`, `meta`, and `options`,
  potentially including upstream credentials. Secure Cuiman launch replaced it
  with a one-shot launch exchange, HttpOnly cookie, and server-side proxy.
- Although the issues were scoped to Cuiman, the parser was removed globally.
  Standalone URL-based service configuration received no equivalent replacement.
- Keep the secure Cuiman flow. The newly agreed static `config.json` service
  entry addresses standalone deployment configuration without reviving generic
  credential-bearing URL serialization.

## Verification already completed

Python, before the latest asset/service design changes:

```text
pixi run test-cuiman --cov=cuiman.api.branding --cov=cuiman.api.config --cov=cuiman.app --cov=cuiman.api.client_app_mixin --cov-report=term-missing
708 passed; all selected modules 100% coverage
pixi run checks
Passed, including mypy
```

The narrowed browser implementation passed TypeScript and ESLint through
`npm run checks`, and `npm run tests`: 200 tests in 45 files. The earlier,
broader browser version had a successful standalone production build; the
narrowed version was not rebuilt. No final design integration has been verified.

The PowerShell `npm` launcher points to a missing roaming npm installation.
Use the installed Node.js npm CLI to run the existing project scripts:

```powershell
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run checks
```

Tests/builds needed sandbox escalation because esbuild could not enumerate a
parent directory. Pixi previously needed escalation for its external cache.

Final verification should cover standalone service precedence, Cuiman isolation,
asset registration/access/MIME handling, optional/malformed config, defaults,
launch/reload behavior, and Jupyter prefixes. Update relevant docs (required by
AGENTS.md), rebuild Cuiman's bundled browser with `npm run eozilla:build`, and
run appropriate frontend/Python checks and the docs build after implementation.

## Git state when this handover was updated

Root HEAD: `09f68ead`. Frontend HEAD: `c195236`. The user plans to commit the
intermediate state; these hashes/statuses may therefore change before resumption.

Root working changes: this handover and `docs/eozilla-app/index.md`; the nested
`eozilla-app/` remains untracked from the root repository's perspective.

IMPORTANT: frontend index and working tree differ. The earlier added files
`src/config/runtime.ts`, `runtime.test.ts`, `startup.ts`, and `startup.test.ts`
are still staged as additions but deleted in the working tree (`AD`).
`src/components/Header.test.tsx` is staged and subsequently modified (`AM`).
Other branding/bootstrap changes are unstaged. Ensure the intended deletions
and updated files are included when committing so the superseded implementation
is not accidentally committed. This session has not changed the index.

No commits, pushes, PR creation, or issue edits were performed in this session.
