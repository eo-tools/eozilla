# Runtime branding and configuration handover

Updated 2026-10-15. Python assets, browser runtime configuration, documentation,
and the bundled browser rebuild are complete. Changes are ready for review.

## Workspace and review state

Work in `C:\Users\norma\Projects\eozilla`; `eozilla-app/` is a separate Git
checkout. At the start of the final integration/documentation step, root HEAD
was `34ae56b1` and frontend HEAD was `c78fac5`. The user committed the earlier
Python and browser checkpoints. This agent has not committed, pushed, created
PRs, or edited issues.

Related issues:

- https://github.com/eo-tools/eozilla/issues/244
- https://github.com/eo-tools/eozilla-app/issues/101

## Implemented contract

- The browser fetches optional app-relative `config.json` before rendering.
  Only HTTP 404 means absent; other load/validation failures show a startup
  error. The fetch explicitly accepts JSON and requests no-store.
- Branding merges field by field with defaults: title `Eozilla`, favicon
  `./eozilla-small.svg`, header emoji `🦖`. Missing/null fields use defaults.
  An icon has exactly one `emoji` or `url`. Image URLs resolve against the
  browser-visible app URL, retaining hosting and Jupyter proxy prefixes.
- Standalone static configuration can include public `service` settings. These
  select a configured instance of the existing custom provider ahead of saved
  selections and prefill the existing authentication form. Credentials retain
  their existing separate session storage; changed connection settings do not
  inherit mismatched saved credentials. No new authentication flow was added.
- Cuiman exchanges the one-shot launch code at `POST ./_cuiman/launch` (204 and
  an HttpOnly cookie), then loads authenticated configuration. `cuiman=1` supports
  reloads. The browser ignores `service` in this mode and uses the existing
  Python-owned proxy. No branding query overrides were added.
- Python branding belongs to `ClientConfig.branding`. `AppImageIcon` accepts
  exactly one `path` or `url`; favicon also accepts a `Path` or a URL string.
  Local files are snapshotted at app-server creation and served at the dedicated
  authenticated favicon/icon endpoints. Missing files warn and omit that
  override; other read errors propagate. MIME types use filename extensions,
  with an octet-stream fallback. Configuration never exposes local paths.
- Saved profiles preserve explicit local `path` values. Partial branding merges
  retain unspecified fields; favicon and icon selections each replace the whole
  value. `AppBranding.from_file()` explicitly loads a branding object, without
  the runtime JSON wrapper. Relative paths use Python's working directory.
- Branding/service-default frontend environment variables have been removed.
  Build metadata remains build-time configuration. Existing presentation and
  secure launch parameters retain their behavior. The removed legacy service
  query protocol has not been restored.

## Documentation ownership

- `docs/eozilla-app/runtime-configuration.md`: canonical deployment example,
  fields/defaults, precedence, asset lifetime/endpoints, and startup behavior.
- `docs/eozilla-app/index.md`: concise app introduction and links.
- `docs/eozilla-app/service-provider.md`: provider lifecycle, authentication,
  and Cuiman launch architecture; references the runtime contract.
- `docs/cuiman/customization.md`: Python branding example and path/URL usage.
- `docs/cuiman/configuration.md`: settings precedence and branding merge rules.
- `docs/cuiman/api.md`: generated public branding-model reference.
- `eozilla-app/README.md`: small standalone example and a link to the full guide.

Keep those roles separate; avoid duplicating the full JSON example and field
reference across the overview, provider guide, and README.

## Verification

Final integration/documentation step:

- `npm run eozilla:build` rebuilt `cuiman/src/cuiman/app/dist` successfully.
- A temporary FastAPI/RemoteState fixture with a stubbed upstream served the
  actual bundled app to Playwright Chromium. Direct and Jupyter-style prefixed
  launches passed: launch-code cleanup, cookie authentication, image rendering,
  favicon MIME/no-store headers, proxy and WebSocket paths, reload, missing-file
  defaults, and consumed-code rejection. Standalone static JSON, service
  precedence, saved-selection preservation, reload, absent config, malformed
  JSON, and unauthenticated Cuiman startup were also checked successfully.
  This exercised mounted proxy paths, not a live JupyterHub or external IdP.
  Temporary servers and fixture files were removed after verification.
- `pixi run test-cuiman --cov=cuiman.api.branding --cov=cuiman.api.config --cov=cuiman.app --cov-report=term-missing`:
  719 passed; all selected modules 100% coverage.
- `pixi run checks` passed, including mypy. Frontend `npm run checks` passed.
- `pixi run build-docs` validates the consolidated documentation with strict
  link/navigation checks.

The preceding browser checkpoint passed 245 Node tests and 41 focused Chromium
loader/header tests. Its full Chromium run also hit unrelated existing harness
failures: replacement of native `window`, Node server-renderer imports in a
browser, and a code-theme timing assertion. Those tests were left unchanged;
the targeted browser checks and real bundled-app integration passed.

## Tooling notes

PowerShell's npm launcher points to a missing roaming installation. Use:

```powershell
& 'C:/Program Files/nodejs/node.exe' 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' run checks
```

Pixi and Vite/Playwright checks required sandbox escalation for their existing
runtime/cache dependencies. Playwright's required Chromium headless shell was
installed during the browser step.

The docs build copies `docs/hooks/download_fonts.py` to `site/hooks/`. Remove
that generated copy before `pixi run checks` to avoid a duplicate-module mypy
error. Do not alter the source hook.
