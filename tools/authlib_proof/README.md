# Authlib lifecycle proof — disposable experiment

This isolated experiment answers the first question in
[the design proposal](../../AUTHLIB_DESIGN.md): can persistent Authlib HTTPX2
clients handle acquisition, expiry, refresh, and signing with a small storage
policy, while keeping the live token usable during a persistence outage?

**Result: yes for the bounded cases below.** Both sync and async clients passed
all scenarios on Windows on 2026-09-09, using Authlib **1.8.0**, HTTPX2 **2.5.0**,
and Python **3.12**. This validates a building block, not the complete Cuiman
integration. The experiment imports no Cuiman code and must not become a second
production authentication implementation.

## Run

From the repository root:

```console
pixi run --manifest-path tools/authlib_proof/pixi.toml proof
pixi run --manifest-path tools/authlib_proof/pixi.toml check
pixi run --manifest-path tools/authlib_proof/pixi.toml format-check
```

The separate manifest and lockfile keep the experiment's dependencies out of the
root environment and Cuiman package. The lock covers the repository's three
platforms; execution was checked only on Windows. Installing dependencies requires
package downloads when uncached. Running the proof itself uses only HTTPX2
`MockTransport`, an in-memory fake store, and fake credentials under `.test` URLs.
No provider, browser, keyring, or external API is contacted.

Sandboxed runs on this machine could not read some packages/tools linked to Pixi's
external cache; approved elevated runs succeeded. Those access failures were not
failures of the proof's lifecycle assertions.

## What ran

Each of these five cases ran through both `OAuth2Client` and `AsyncOAuth2Client`:

| Case | Observed result |
| --- | --- |
| Password acquisition, then expiry and refresh-token rotation | Two API requests used access-1, then access-2; refresh-2 was saved |
| The same flow with unavailable storage during refresh | One storage warning; the second API request still succeeded with access-2 |
| Client credentials, then expiry | Authlib fetched a second client-credentials token and notified the callback |
| Client credentials with unavailable storage during reacquisition | One storage warning; the second API request still succeeded |
| Refresh response omitted its refresh token | Authlib retained refresh-1 in the live token and saved snapshot |

All **10 scenarios passed**. Ruff lint and formatting checks also passed.

Each case keeps one Authlib client for acquisition and both API requests. The
experiment advances Authlib's clock reference past expiry; it does not expire
tokens by manually editing the token mapping or sleeping. The mock provider
validates the grant request body, client-secret POST authentication, refresh
credential, and bearer header on each protected request. Unknown destinations
fail an assertion.

Additional assertions verify:

- `fetch_token` installs the token but does **not** call `update_token`. An explicit
  save after initial acquisition is necessary.
- During refresh/reacquisition, `update_token` receives the live `client.token`
  after installation, plus the prior refresh/access token identifier.
- Access token, applicable refresh token, type, scope, duration, and normalized
  absolute expiry survive JSON snapshot persistence.
- Loading a saved snapshot later preserves its absolute expiry; it does not
  restart the original duration.
- An explicit save during an outage raises `StorageUnavailable` while leaving
  the live token intact. After storage recovers, saving that same token succeeds
  without another provider exchange. This exercises the proposed save policy,
  not the real `cuiman login` command.
- Every client closes, including the async clients through `aclose()`.

## Representative failure trace

```text
password issued access-1
saved access-1
API accepted access-1
clock advanced past expiry
refresh_token issued access-2
callback sees live access-2
save unavailable                  # warning captured and checked
API accepted access-2             # authentication remains usable
save unavailable
explicit save reported failure
saved access-2
explicit save recovered without a provider exchange
```

The script prints each trace and its complete **fake** saved token. During the
outage, the fake store retains access-1 while Authlib owns access-2; after the
explicit retry, both contain access-2. The real keyring's partial-write or cleanup
failure behavior is not represented by this fake store.

## How much application code was necessary

The proposed application policy is the `persist_token` function in
[proof.py](proof.py): copy the mapping for storage, catch the expected storage
exception, and either warn or propagate according to whether persistence was
explicitly required. Callback wiring connects that policy to Authlib; async use
supplies an async callback. The fake async callback does no blocking keyring I/O.

No Authlib subclass, custom token model, expiry algorithm, refresh request
implementation, request preflight layer, or renewal lock was needed for these
sequential cases. Authlib's native client-credentials metadata also handled
reacquisition. Most of the script is the fake provider, fake store, and assertions.

**Design implication:** start the production client-credentials slice with direct
Authlib client construction and callback wiring. Add a subclass only when a
specific remaining application policy needs an extension point. The earlier
proposal's thin subclasses are a possible tool, not a prerequisite demonstrated
by this proof.

## Limits and next review

This does not establish concurrent renewal, cancellation or shielding during
real storage I/O, resource-401 replay, password recovery from `invalid_grant`,
malformed provider response handling, custom token headers, a client-credentials
provider returning a refresh token, OIDC/PKCE/ID-token validation, or proxy work
across threads/event loops. Those remain separately reviewed steps. Warning
behavior was tested with warnings enabled; Python callers can choose to promote
warnings to exceptions.

Production Cuiman, its dependencies, `tools/gen_client.py`, and the generated
clients were not changed. No production coverage, full-workspace tests, or docs
build was run because this step changes only the isolated experiment.

The next proposed step is the first production client-credentials slice, covering
initialization, requests, expiry, persistence, and close through the handwritten
mixins and transport. Any necessary generated-client structure changes must come
from `tools/gen_client.py`, followed by `pixi run gen-client`. Review this proof
before beginning that slice.
