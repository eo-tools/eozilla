# Authentication lifecycle

Cuiman uses one authentication lifecycle for the Python clients, CLI, and
launched-app proxy. The implementation currently uses HTTPX2 and the existing
protocol helpers. Authlib adoption is deferred to a separate change.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| `auth.config` | Authentication settings, credentials, header rendering, and the optional persistence hook. Its renewal methods delegate to `auth.session`. |
| `auth.session` | Decide whether credentials are sufficient, select token acquisition or renewal, and commit credentials through one shared path. |
| `auth.tokens.TokenResult` | Protocol-independent result containing access and optional refresh tokens. It remains exported from `cuiman.api.auth`. |
| `auth.login`, `auth.oauth2`, `auth.oidc`, and async counterparts | Execute protocol requests and return token results. They do not update live configuration or persist credentials. |
| `auth.interactive` | Explicit credential prompts and browser login, including callback handling and cancellation. Returns a candidate configuration for the session to commit. |
| `auth.secret_store` | OS-keyring storage, including Windows entry-size handling. |
| Client mixins | Explicit versus automatic login, coordination of asynchronous initial login, and lazy transport creation. |
| HTTP transport and app proxy | Send requests and retry one 401 response using the session's optional renewal callback. They do not select grants or persist tokens. |

The public configuration methods that create renewal callbacks remain available
as delegates. Callers can also use the session callback factories directly.
No provider registry or additional backend abstraction is needed at this stage.

## Token updates

Initial acquisition and renewal use the same protocol selection and commit
rules:

- OAuth2 password grants use an existing refresh token when available;
  otherwise they obtain tokens using the supplied credentials.
- If a refresh request returns HTTP 400 with OAuth2 `invalid_grant`, password
  grants can recover with one fresh login using available username/password
  credentials. OIDC and password grants without those credentials raise
  `LoginRequiredError` with instructions for explicit fresh login. Other
  errors propagate without recovery, and API calls never start interaction.
- Client-credentials grants obtain a new access token using client credentials
  and ignore any refresh token returned by the provider.
- OIDC renewal uses the configured issuer and refresh token.
- A missing or empty refresh token in a successful renewal preserves the
  previous refresh token for password grants and OIDC. Fresh login, including
  recovery and `login(force=True)`, starts without tokens and therefore cannot
  retain a rejected or deliberately bypassed refresh token.
- Credentials are first saved through the optional persistence hook using a
  candidate configuration. Only a successful save publishes those values to
  the live configuration. Unrecovered protocol failures and cancelled requests do not
  publish token updates.

A persistence failure leaves local credentials unchanged. It cannot undo token
rotation already performed by a remote provider; interactive login may be
needed if that provider no longer accepts the previous refresh token.

`login(force=True)` acquires fresh authentication on a temporary configuration
without access or refresh tokens. It respects `interactive` and `no_browser`,
then commits all resulting secrets through the shared persistence operation.
The client mixin updates an existing HTTPX2 transport only after login succeeds.
These recovery and interaction policies remain Cuiman responsibilities when
the underlying protocol helpers are replaced by Authlib.

The current implementation retains its existing 401-triggered renewal and
single retry. It does not yet track token expiry or coordinate concurrent
renewals. Initial asynchronous login remains coordinated by the client mixin.
Static access tokens have no renewal callback and never cause automatic
interaction. See [Remote notebooks](./configuration.md#remote-notebooks).

## Future Authlib integration

A separate implementation change can replace OAuth/OIDC protocol helpers and
connect Authlib's token lifecycle at the session boundary. Configuration,
interaction policy, and keyring persistence remain Cuiman responsibilities.
That change should verify:

- HTTPX2 compatibility for synchronous and asynchronous clients;
- browser authorization with PKCE and remote CLI device authorization;
- expiry metadata, refresh coordination, and the existing 401 retry policy;
- preservation of refresh-token rotation and persistence-failure behaviour;
- Keycloak interoperability and injected-token notebook use.

The intended benefit is deletion of custom protocol and lifecycle code. Avoid
retaining a second independent token manager alongside the library. Device
authorization, automatic expiry handling, and notebook token-provider callbacks
are not introduced by this preparation.
