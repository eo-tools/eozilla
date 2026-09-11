# Handover: application-specific Cuiman configuration

## Status and purpose

The user endorsed the recommendation below and wants to continue in a fresh
session. This session was dedicated to authentication. This document records
the configuration design discussion; the proposed interface is not implemented.

At handover, HEAD is `6934ab5` (configuration-file validation). The tracked
working tree was clean before adding this file. Untracked `eozilla-app/` and
`notebooks/Untitled.ipynb` are unrelated existing content.

The user's priorities are less code to maintain, easier application integration,
and consistent configuration/authentication across the CLI, Python clients, and
app. Prefer replacing redundant mechanisms to adding compatibility layers.

## Problem and verified current behavior

Sen4CAP subclasses `ClientConfig` to customize Pydantic `model_config`, including
`env_prefix="SEN4CAP_"`, `env_file=".env"`, and `extra="allow"`. Today it must
assign its default configuration instance and configuration path to the base
`ClientConfig` class. Importing the application therefore changes process-wide
Cuiman behavior.

Assigning `Sen4CAPConfig.default_config` or `.default_path` instead does not
update the base class: Python subclass assignments shadow inherited attributes.
Both standard clients call `ClientConfig.create()`. Its schema selection uses
`type(ClientConfig.default_config)`, while defaults and the path are still read
through the base class. Passing `Client(config=Sen4CAPConfig(...))` does not
currently select the subclass schema. Direct `Sen4CAPConfig.create()` calls do
use subclass attributes, but that does not configure the standard clients/CLI.

The user finds this confusing and wants each application to have its own
namespace instead of modifying `ClientConfig` globally.

## Endorsed direction

Use the application's configuration class as its namespace. Introduce an
explicit `config_type` parameter shared by `Client`, `AsyncClient`, and
`new_cli`. Ordinary Pydantic field defaults replace the separate
`default_config` instance. Remove `default_config` and `_configured_type()`
once their callers use the selected class directly.

Proposed application integration (illustrative, not a currently usable interface):

```python
from pathlib import Path
from typing import Any, ClassVar

from pydantic_settings import SettingsConfigDict

from cuiman.api import AsyncClient, Client, ClientConfig
from cuiman.api.auth import AuthConfig, LoginAuthConfig
from cuiman.cli import new_cli

from .opener import Sen4CAPJobResultsOpener


class Sen4CAPConfig(ClientConfig):
    model_config = SettingsConfigDict(
        env_prefix="SEN4CAP_",
        env_file=".env",
        extra="allow",
    )

    default_path: ClassVar[Path] = Path.home() / ".sen4cap-client"
    api_url: str | None = "http://localhost:8080/process/"
    auth: AuthConfig = LoginAuthConfig(
        login_url="http://localhost:8080/auth/login",
        access_token_header="X-Auth-Token",
    )


Sen4CAPConfig.register_job_result_opener(Sen4CAPJobResultsOpener)


def create_client(**config: Any) -> Client:
    return Client(config_type=Sen4CAPConfig, **config)


def create_async_client(**config: Any) -> AsyncClient:
    return AsyncClient(config_type=Sen4CAPConfig, **config)


cli = new_cli(name="sen4cap-client", config_type=Sen4CAPConfig)
```

Users keep simple calls such as `create_client()`,
`create_client(auth=credentials)`, and `client.show_app()`.

The selected class owns the schema, field defaults, environment and dotenv
settings, default file path, and application extensions. Plain Cuiman defaults
to `ClientConfig`; importing Sen4CAP leaves it unchanged.

One resolver combines class defaults, configuration-file values, environment
settings, and explicit overrides. CLI commands and both Python clients use that
resolver. The app retains its originating client's configuration type and
resolved configuration when constructing backend clients.

When `config_type` is omitted and `config` is an instance, infer the type from
that instance. If both are supplied, require compatible types. Define the exact
compatibility rule during implementation and test it; the discussion did not
settle subtype-versus-exact-match semantics.

## Implementation details to resolve carefully

- Preserve partial authentication overrides until sources have been combined;
  validating each source independently can reject valid partial credentials.
  Include class field defaults even though existing serialization helpers omit
  defaults and unset values. Avoid constructing a default settings instance
  that reads environment sources prematurely.
- Make `.env` work through the same resolver without requiring the wrapper to
  construct `Sen4CAPConfig()` first. Specify and test dotenv precedence relative
  to the persistent file and process environment; exact dotenv precedence was
  not settled in the discussion.
- Carry the selected type and source path through wrapping an already resolved
  configuration. Avoid a second resolution that switches application defaults,
  overwrites explicit settings, or loses credential persistence hooks.
- Audit mutable class attributes for application isolation. `return_type_map`
  is currently an inherited dictionary. The opener registry factory is already
  a cached classmethod keyed by `cls`; verify and preserve that isolation rather
  than replacing it speculatively. Decide inheritance behavior for application
  subclasses and test that registrations cannot leak into unrelated clients.
- Keep one shared implementation for sync, async, CLI, and app configuration.
  This change should simplify configuration management, not introduce another
  configuration manager or duplicate authentication logic.

## Existing behavior to preserve

- An auth model or auth dictionary containing `auth_type` replaces previous
  auth settings. A dictionary without `auth_type` merges into the selected
  configuration; partial `None` values are ignored. Matching keyring secrets
  fill missing credentials under the existing rules.
- Config files are validated against the application's selected schema.
  Parsing/validation failures produce exactly:
  `Deprecated or illegal configuration file, please run the 'configure' command.`
  Valid files are accepted without legacy-field heuristics. Reads do not rewrite
  files; writes omit credentials. `configure` can recreate invalid files from
  defaults. Missing/empty files remain unconfigured; access errors propagate.
- URL handling remains role-specific: processing endpoints are appended to
  `api_url`; login/token URLs retain meaningful trailing slashes; issuer
  identity remains exact. The notebook app's processing-root 404 was fixed.
- Interactive `configure` requires a terminal for missing options. Fully
  specified noninteractive commands work; notebook users can call
  `configure_client_with_prompt()` directly. Preserve the fix for hanging
  `!cuiman configure` cells.
- Keep the completed Authlib architecture. External JupyterHub token-provider
  integration is separate work tracked in
  <https://github.com/eo-tools/eozilla/issues/211>.

## Starting points and completion criteria

Read the root `AGENTS.md`, then inspect:

- `cuiman/src/cuiman/api/config.py` and its tests for settings resolution,
  persistence, schema selection, and application extensions.
- `cuiman/src/cuiman/api/client.py`, `async_client.py`, and
  `tools/gen_client.py`: client files are generated, so update the generator.
- `cuiman/src/cuiman/cli/cli.py`, `config.py`, and `client.py` for all CLI paths,
  including configure/login/logout.
- `cuiman/src/cuiman/api/client_app_mixin.py` and the backend client creation
  paths it reaches for app propagation.
- `docs/cuiman/configuration.md`, `authentication.md`, and `cli.md` for current
  documented behavior.

Suggested implementation slices, subject to inspection in the next session:

1. Select configuration classes explicitly and resolve their field defaults and
   settings sources. Complete when two application types and plain Cuiman can
   coexist with independent paths, environment prefixes, and schemas.
2. Propagate selection through sync/async clients, CLI, and app. Complete when
   all entry points retain application identity, partial auth overrides work,
   and extension registrations remain isolated.
3. Remove redundant global-default machinery, document the Sen4CAP integration,
   and validate. Complete when relevant tests cover the isolation and source
   precedence rules, generated files agree with their source, and project checks
   and documentation build pass.

Before this handover, all 550 Cuiman tests passed, with 100% coverage for
`cuiman.api.config` and `cuiman.cli.config`; project checks and docs build passed.
Use repository Pixi tasks for validation. Update the changelog and configuration
documentation for the new interface. Keep this work separate from further auth
features, and remove or archive this handover when its content is incorporated.
