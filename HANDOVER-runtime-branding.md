# Runtime branding handover

## Resume here

Work in `C:\Users\Norman\Projects\eozilla`. Read `AGENTS.md` and the two issues:

- https://github.com/eo-tools/eozilla/issues/244
- https://github.com/eo-tools/eozilla-app/issues/101

The user requested at most four steps, with their review before continuing:

1. Design (agreed, with the refinements below).
2. Cuiman implementation (implemented and tested; awaiting final review).
3. Browser implementation (not started).
4. Documentation, bundled app rebuild, and integration verification (not started).

Present the current step for review and wait for authorization before starting
step 3. This handover request does not authorize proceeding to step 3.

## Agreed design

The general browser configuration source is `./config.json`, resolved relative
to the browser-visible app URL. This replaces the initial proposal to return
branding in the launch exchange and add `/_cuiman/config`.

- Standalone deployments may serve a static `config.json` beside the app.
- Cuiman serves a dynamic, session-authenticated `GET /config.json`.
- Cuiman first exchanges the one-shot launch code at `POST ./_cuiman/launch`,
  retaining HTTP 204 and its existing HttpOnly cookie. The browser then loads
  configuration. After reload, the `cuiman=1` marker and session cookie suffice.
- Configuration is optional: the user explicitly emphasized that the endpoint
  may not exist at all. Treat HTTP 404 as absent configuration and render using
  built-in defaults plus query overrides. The last proposed behavior for other
  HTTP failures and malformed configuration is a clear configuration error;
  avoid silently treating an expired Cuiman session as an optional-file 404.
- Precedence: query overrides > `config.json` > built-in defaults; merge branding
  field by field. Proposed query names are `title`, `favicon`, `iconEmoji`, and
  `iconUrl`, alongside existing presentation parameters. A JSON-valued
  `branding` query parameter was not selected.
- Built-in branding: title `Eozilla`, favicon `./eozilla-small.svg`, emoji `🦖`.
- Standalone JSON may additionally contain public `defaultService` metadata.
  Its exact field whitelist still needs to be made concrete in step 3. Credentials
  must never be supplied via query parameters or public JSON. Cuiman mode retains
  its dedicated existing service proxy and server-side credentials. Saved
  standalone provider selections take precedence over deployment defaults.
- Resolve relative assets against the app URL, preserving Jupyter proxy prefixes.
  Absolute HTTP(S) URLs stay absolute; leading `/` has normal origin-relative
  semantics. URLs do not publish files from the Python host's filesystem.
- Resolve configuration before React renders and apply title, favicon, and header
  icon consistently. Replace branding/service-default `.env` usage; app version
  build metadata may remain.

Runtime JSON contract:

```json
{
  "branding": {
    "title": "Sen4CAP",
    "favicon": "./sen4cap.svg",
    "icon": {"emoji": "🌍"}
  }
}
```

An image icon uses `{"url":"./logo.svg"}` instead. The icon has exactly one
alternative. All branding fields are optional. Missing/null fields fall back.

## Current Cuiman implementation

The user corrected the original interface: branding belongs to `config.branding`,
not a separate argument beside `config`. The current implementation reflects this:

- `cuiman/src/cuiman/api/branding.py`: public Pydantic models `AppBranding`,
  `AppEmojiIcon`, `AppImageIcon`; strict nonempty strings and forbidden extra
  fields. Re-exported from `cuiman.app`.
- `AppBranding.from_file(path)`: explicitly reads UTF-8 JSON, expands `~`,
  propagates filesystem/validation errors. Its file contains branding fields
  directly, e.g. `{"title":"Sen4CAP"}`, rather than the runtime JSON wrapper.
  Relative asset URLs remain relative to the browser app, not the file.
- `cuiman/src/cuiman/api/config.py`: `ClientConfig.branding` defaults to an
  independent empty `AppBranding`. Uses existing profile, dotenv, environment,
  explicit settings, subclass defaults, and snapshot resolution. Empty branding
  is omitted from persisted profiles. Partial branding merges preserve other
  fields; icon overrides replace the whole icon to support emoji/image switches.
- `show_app()` and `serve()` read branding from the configuration; the separate
  branding parameter has been removed.
- `cuiman/src/cuiman/app/launch.py`: snapshots branding when constructing the
  app server; `GET /config.json` requires a valid session, returns only
  `{"branding": ...}`, and uses `Cache-Control: no-store` for success and
  authentication failures, including behind a path prefix. Route precedes the
  static app mount. Launch response remains 204.

No file is loaded automatically from `~/.eozilla/app-config.json`. The user
accepted explicit `AppBranding.from_file(path)` and requested `config.branding`.

```python
from cuiman import Client, ClientConfig
from cuiman.app import AppBranding

config = ClientConfig(
    branding=AppBranding.from_file("~/.sen4cap/app-config.json"),
)
client = Client(config=config)
app = client.show_app()
```

## Verification completed

Before implementation, existing app tests and client-app-mixin tests passed
with 100% coverage. After the final configuration revision:

```text
pixi run test-cuiman --cov=cuiman.api.branding --cov=cuiman.api.config --cov=cuiman.app --cov=cuiman.api.client_app_mixin --cov-report=term-missing
708 passed; all selected modules 100% coverage

pixi run checks
Passed, including mypy
```

Changed tests also passed Ruff lint and scoped formatting. Tests cover profile
round trips, source precedence, application defaults/prefixes, explicit file
loading, invalid data, session/reload behavior, credential exclusion, snapshots,
server isolation, static-route precedence, and Jupyter proxy prefixes.

Pixi needed sandbox escalation for its external package cache; sandboxed runs
reported failure creating the uv cache directory. Approved escalated runs worked.

## Browser work to inspect after approval

The separate nested checkout `eozilla-app/` has no implementation changes from
this session. Relevant files:

- `src/main.tsx`: exchanges launch code, strips it, registers Cuiman-only provider,
  and derives service/WebSocket URLs from the visible app URL.
- `src/config/bootstrap.ts`: existing presentation/mode query parsing.
- `src/config/cuimanLaunch.ts`: currently accepts successful launch responses
  without a body; keep compatible with 204.
- `src/components/Header.tsx`: title/icon currently read from Vite environment;
  image detection currently checks only a leading slash.
- `index.html`: build-time title/favicon placeholders.
- `src/service/providers/url.ts`: build-time standalone service defaults.

Concentrate loading, validation, precedence, and asset resolution in the runtime
configuration module. Add tests for missing endpoint, partial config, malformed
responses, query overrides, pre-render branding, reloads, and prefixed URLs.
Use the frontend scripts in `package.json` for checks and tests.

Step 4 must update relevant `docs/eozilla-app/` pages (required by `AGENTS.md`),
the Cuiman app/configuration/customization guides, and any stale frontend setup
instructions. Rebuild the bundled browser app in `cuiman/src/cuiman/app/dist`
using the existing frontend build script and run relevant checks/docs build.

## Git state at handover (2026-10-14)

Root HEAD: `6d070e6c`, a user-created commit containing the current Cuiman work.
Its commit message describes the earlier separate-argument design; use source
code as the authority for the current interface. Frontend HEAD: `c195236`.

Root status showed:

```text
AD cuiman/src/cuiman/app/branding.py
?? docs/research/
?? eozilla-app/
```

The obsolete `app/branding.py` is staged as an addition but deleted in the working
tree; its current implementation is under `api/branding.py`. The index was left
untouched. Inspect this state with the user before preparing a commit so the old
file is not accidentally restored. Preserve existing research files and the
nested checkout. This session did not commit, push, open PRs, or modify issues.
