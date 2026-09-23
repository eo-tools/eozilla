# JupyterHub authentication — breakpoint and handover

Recorded: 2026-09-23.

## Workspace and current state

- Repository: `C:\Users\norma\Projects\eozilla`.
- Branch: `forman/211-use_jupyter_auth`.
- Issue: https://github.com/eo-tools/eozilla/issues/211.
- HEAD when this note was written: `5c68ed6f` (merge of `main`).
- All four implementation slices are complete. Stop here for review; the improvements below are recommendations, not instructions to implement them automatically.
- The working tree has a pre-existing modification to `CHANGES.md` and untracked nested directories `eozilla-app/` and `eozilla-workorder/`. Preserve these. This handover note is the only change made for the handover request.
- A PR description was drafted in the conversation. No PR was created by the assistant during this session.

The assistant's default tool directory may be `C:\Users\norma\Documents\Codex`; explicitly select the repository above. Earlier work accidentally targeted a different checkout. Do not repeat that mistake.

## Agreed interface and behavior

- Use the existing `auth` argument for configuration models, dictionaries, or a native `httpx2.Auth` adapter. Do not reintroduce a separate public `http_auth` argument.
- `auth_type="auto"` is the default for new configurations. It discovers an available authentication mechanism; currently only JupyterHub is supported. The name deliberately allows other mechanisms in the future.
- `auth_type="none"` skips discovery and uses anonymous access. Existing profiles explicitly selecting `none` retain that behavior.
- `auth_type="jupyter"` requires JupyterHub authentication and fails if its environment or upstream token is unavailable.
- The separate `discover_jupyter_auth` setting and CLI flags were removed in favor of these auth types.
- For `auto`, both Hub environment variables absent means no candidate and anonymous access. Partial/malformed settings or a failed lookup raise an error. There is no anonymous fallback after detecting a broken mechanism.
- Construction performs no network I/O. Discovery occurs when an operation needs client authentication, and successful selection is retained for that client. Create a new client after changing its environment or authentication settings.
- Constructor `auth=None` retains configured authentication. Per-request `auth=None` disables automatic authentication for that request. Explicit request authentication or an Authorization header overrides client authentication.
- JupyterHub login verifies upstream-token availability at that moment. It does not prove that a processing service will accept the token.
- Each authenticated processing request retrieves the current upstream access token from the Hub. Cuiman does not cache tokens, implement refresh scheduling, or replay rejected processing requests. The Hub owns refresh.
- Hub credentials and upstream tokens are not persisted by Cuiman or supplied to the app browser as authentication credentials.
- Python and app requests share their owner's HTTP session. Stopping an app that borrows a client leaves the client usable; closing/logging out of the owner makes later app requests fail. Standalone app servers close their owned clients.
- Logout for `auto` and `jupyter` does not access the keyring or sign out of JupyterHub, including before discovery.

## Implementation landmarks

- `cuiman/src/cuiman/api/auth/config.py`: `AutoAuthConfig`, `NoAuthConfig`, `JupyterAuthConfig`, and the discriminated auth union.
- `cuiman/src/cuiman/api/auth/jupyterhub.py`: environment detection, the shared HTTPX2 auth flow, Hub response validation.
- `cuiman/src/cuiman/api/client_mixin_base.py`: shared auth selection, precedence, login verification helpers, and logout policy.
- `cuiman/src/cuiman/api/client_mixin.py` and `async_client_mixin.py`: mode-specific I/O and app callbacks.
- `cuiman/src/cuiman/api/config.py` and `defaults.py`: configuration defaults.
- `cuiman/src/cuiman/cli/config.py` and `cli.py`: configuration and login/logout behavior.
- `cuiman/tests/api/auth/test_jupyterhub.py`: adapter, discovery, precedence, configuration, and CLI tests.
- `cuiman/tests/app/test_jupyterhub.py`: app integration and lifecycle tests; the shared simulated Hub lives in `cuiman/tests/conftest.py`.
- `docs/cuiman/authentication.md`, `configuration.md`, and `guides/app.md`: behavior, setup, and notebook usage.

The sync and async client files are generated. Change `tools/gen_client.py` and regenerate them; do not put handwritten behavior into generated clients. New client behavior belongs in mixins, with common sync/async policy factored into shared code. No discovery plugin framework or generic verification hierarchy is needed yet.

## Validation at the breakpoint

The final slice-4 run passed **950 Cuiman tests**. `pixi run checks` passed, including type checks over 123 source files. Coverage was **100%** for `cuiman.api.auth.jupyterhub`, `cuiman.api.client_mixin_base`, and `cuiman.app.launch`.

Commands used:

```text
pixi run test-cuiman --cov=cuiman.api.auth.jupyterhub --cov=cuiman.api.client_mixin_base --cov=cuiman.app.launch --cov-report=term-missing
pixi run checks
```

Tests use simulated Hub and processing-service responses, with real app routes and lifespan handling. No live JupyterHub deployment was tested. The successful run preceded the subsequent merge of `main` now at HEAD; it is not a claim that the merged HEAD has been revalidated. Existing warnings included a Typer deprecation, deliberate opener-test warnings, and pytest-cache write permissions.

## Design assessment and recommended follow-ups

The design is sound and not substantially overengineered. Reusing `auth` and replacing the discovery flag with `auto`/`none`/`jupyter` simplified the interface. One HTTPX2 flow, shared mixin policy, and one owner for Python/app requests avoid duplicate mechanisms. Leaving refresh with the Hub avoids a cache and scheduler that would need their own lifecycle.

Prioritized improvements:

1. **Clarify CLI outcomes.** It currently prints “Login completed” even when `auto` selects anonymous access. Prefer messages such as “Using anonymous access” and “JupyterHub authentication verified.” “Logged out” should not imply signing out of the Hub. Keep credential/provider details out of messages.
2. **Run a real Hub smoke test.** Verify the documented permissions, auth-state access, refresh behavior, Python requests, and app launch together in a representative deployment. This is the largest remaining confidence gap; coverage does not replace it.
3. **Consider read-only auth introspection.** Configuration remains `auto` after selection. A small way to inspect the selected mechanism could help troubleshooting without exposing credentials. Avoid a broader diagnostics subsystem unless needed.
4. **Measure lookup overhead.** Every processing request adds a Hub lookup; explicit login performs a separate check. Measure polling-heavy workloads before introducing caching or changing token ownership.
5. **Revisit the verification interface only when a second mechanism arrives.** The shared mixin currently calls the adapter's private `_user_request()` and `_access_token()` helpers. This is manageable coupling today. A second mechanism would provide evidence for a shared verification interface and an explicit discovery order.

Later documentation decision: do not promote per-request authentication overrides as a Cuiman feature. Remove examples and prominent precedence descriptions; retain only a brief HTTPX2 forwarding note in the API reference. Runtime behavior and regression tests remain unchanged.

Recommended next work, if requested: improve CLI wording and perform the live deployment smoke test. Keep the architecture; do not add speculative abstractions. Recheck the current diff and merged HEAD before continuing.
