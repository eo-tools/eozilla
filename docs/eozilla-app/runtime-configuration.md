# Runtime Configuration

Eozilla App reads optional `./config.json` before rendering. Branding and the
intended standalone connection can change without rebuilding the app.

| Deployment | Configuration source | Service connection |
| --- | --- | --- |
| Standalone | Static `config.json` beside `index.html` | Optional `service` settings; otherwise the saved selection or service dialog |
| Cuiman | Python's authenticated `config.json` | Python-owned proxy; JSON `service` settings are ignored |

## Standalone setup

Deploy `config.json` beside `index.html`, along with any referenced images:

```json
{
  "branding": {
    "title": "Sen4CAP",
    "iconPosition": "before",
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

Both sections are optional. For Vite development, put the file and images in
`public/`; they are copied into the build. A deployer can also add or replace
them directly in the deployed app.

## Branding

Missing or null fields fall back individually:

| Field | Value | Default |
| --- | --- | --- |
| `title` | Nonempty browser-tab and header title | `Eozilla` |
| `favicon` | Image URL | `./eozilla-small.svg` |
| `icon` | Exactly one of `{"emoji":"🌍"}` or `{"url":"./assets/logo.svg"}` | `{"emoji":"🦖"}` |
| `iconPosition` | `"before"` or `"after"` the header title in reading order | `"after"` |

Icon position applies to both emoji and images. It does not change the
browser-tab title or favicon. Invalid positions produce a configuration error.

Relative image URLs resolve against the browser-visible app URL, preserving
hosting and Jupyter proxy prefixes. Leading `/` is origin-relative; external
HTTP(S) URLs also work. A URL does not publish a Python-local file.

## Standalone service settings

A `service` entry selects **Configured Service** ahead of a saved choice and
prefills its existing connection form. Starting the app does not replace the
saved selection. Without an entry, the app uses its saved selection or opens
the usual service dialog.

Only public connection settings belong in this file:

| Fields | Purpose |
| --- | --- |
| `apiUrl` | Required API base URL |
| `authType` | `none` (default), `basic`, `token`, `login`, `oauth2`, or `api-key` |
| `loginUrl` | Required for proprietary `login` authentication |
| `clientId`, `oauth2Protocol` | Public OAuth2 client ID and protocol: `oidc` (default) or `oauth2` |
| `authorizationServerUrl` | Required OIDC issuer URL |
| `authorizationEndpoint`, `tokenEndpoint` | Required endpoints for plain OAuth2 |
| `oauth2Scopes` | Space-separated OAuth2/OIDC scopes |
| `useBearer`, `accessTokenHeader`, `apiKeyHeader` | Public token/header settings |

Service URLs must be absolute HTTP(S) URLs without embedded credentials.
OAuth2 requires a public client ID plus the endpoints appropriate to its
protocol. Unknown fields and credential fields are rejected.

Users authenticate through the existing service dialog and
[authentication flows](service-provider.md#custom-service-authentication).
Do not include passwords, access/refresh tokens, API keys, or client secrets in
the JSON. Saved session credentials are reused only when the saved provider
and configured public settings match; changing a configured setting does not
carry the old connection's credentials into the new one.

## Cuiman and Python-local images

Set `ClientConfig.branding` in Python; see the
[Python example](../cuiman/customization.md#browser-branding-and-local-images).
`AppImageIcon(path=...)` supplies a local file, while `AppImageIcon(url=...)`
supplies a browser URL. Favicon also accepts `Path(...)` or a URL string.

Cuiman snapshots local files when its app server starts. Relative paths use
Python's working directory, and `~` is expanded. Restart the server to pick up
file changes. Missing files warn and leave the browser default in place;
other file-read errors propagate.

The snapshots are served at `/_cuiman/assets/favicon` and
`/_cuiman/assets/icon` using the existing launch-session authentication.
`config.json` contains app-relative URLs rather than local filesystem paths.
Configuration and asset responses use `Cache-Control: no-store`. Asset MIME
types come from filename extensions, with `application/octet-stream` as the
fallback.

The browser exchanges its one-shot launch code before loading configuration.
Python owns the effective branding, connection, and credentials; a JSON
`service` entry is ignored. See the
[Cuiman launch architecture](service-provider.md#cuiman-launched-mode) for the
cookie, proxy, and reload sequence.

## Startup behavior and migration

Only HTTP 404 means the configuration file is absent and defaults should be
used. Other HTTP failures, network errors, invalid JSON, and invalid settings
produce a startup error. Static hosting must return a real 404 for a missing
JSON file rather than its HTML SPA fallback. The loader requests JSON with
`cache: "no-store"`; Cuiman authentication failures remain startup errors.

Branding and service-default `VITE_*` environment variables have been replaced
by runtime configuration. Version/build metadata remains build-time
configuration. Branding query overrides and the old credential-bearing
`service` query parameter are not supported. Existing presentation and launch
parameters (`compact`, `debug`, `scheme`, `launch`, `cuiman`, `ws`, and `proxy`)
retain their behavior.
