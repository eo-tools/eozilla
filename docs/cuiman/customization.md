# Cuiman Customization

Applications can create their own clients using `cuiman` under the hood. 
For this, an application defines a configuration class that owns its settings
namespace and default values. Importing that application never changes the
process-wide defaults used by plain `cuiman` or another application.

This is best explained by an example. In the following we explain 
the client customization by a hypothetic processing system "Anolis"
that should get its own `anolis-client`.

The `cuiman` API allows for the following customizations:

1. The `cuiman.api.ClientConfig` is a 
   [pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
   class. It can be used as base class and then configured with a custom 
   `pydantic_settings.SettingsConfigDict` instance.
2. Ordinary Pydantic field defaults and a `default_path` class attribute define
   application defaults and profile persistence.
3. Applications can customize the way how job results are opened.
4. Applications can create their own CLI instance with custom settings.
5. Applications can customize the way the process input GUIs are generated.


## API customisation

In a module `src/anolis_client/api.py`:

```python
from pathlib import Path
from typing import Any, ClassVar

from pydantic_settings import SettingsConfigDict
from cuiman.api import AsyncClient, Client, ClientConfig
from cuiman.api.auth import AuthConfig, NoAuthConfig
from cuiman.cli import new_cli

from .opener import AnolisJobResultsOpener

# Custom configuration class
class AnolisClientConfig(ClientConfig):
    model_config = SettingsConfigDict(
        env_prefix="ANOLIS_",
        env_file=".env",
        extra="allow",  # base ClientConfig uses "forbid"
    )

    default_path: ClassVar[Path] = Path.home() / ".anolis-client"
    display_name: ClassVar[str | None] = "Anolis"
    cli_name: ClassVar[str | None] = "anolis-client"
    api_url: str | None = "https://anolis.api.org/process-api/v1"
    auth: AuthConfig = NoAuthConfig()
    extra_job_result_openers = [AnolisJobResultsOpener]


def create_client(**config: Any) -> Client:
    return Client(config_type=AnolisClientConfig, **config)


def create_async_client(**config: Any) -> AsyncClient:
    return AsyncClient(config_type=AnolisClientConfig, **config)


cli = new_cli(name="anolis-client", config_type=AnolisClientConfig)
```

`display_name` supplies the application name for notebook links, browser debug
messages, and app-launch errors. `cli_name` optionally adds a login command to
Python API errors; leave it unset for applications without a CLI. Both are class
metadata, excluded from environment settings and saved profiles. Without them,
messages use neutral wording. Low-level credential-storage errors also use
neutral wording, including errors raised before configuration can be loaded.

CLI recovery messages always use the name passed to `new_cli()`, even when it
differs from `config_type.cli_name`. Creating a CLI does not modify the config
class or other clients. With a custom version, `--version` prints
`anolis-client <application-version> (cuiman <library-version>)`.

`config_type` selects the schema, field defaults, dotenv and environment
settings, profile path, and result-opening extensions for a client or CLI.
When a `config` instance is supplied without `config_type`, its concrete type
is inferred. Supplying both requires the exact same type, which prevents one
application from silently reading another's profile or environment namespace.

Sources resolve once in this order, from lowest to highest precedence: field
defaults, persistent configuration file, `.env`, process environment, supplied
configuration object, and explicit client keyword arguments. Authentication
partials are merged before validation, so a `.env` token can supplement public
provider settings held in a profile.

Subclasses may introduce required fields and default factories. Effective settings
are validated after sources are merged; Cuiman does not construct an empty
application configuration to obtain defaults. Existing profiles must still be
valid against the selected application schema on their own.

Dotenv files use Pydantic Settings' `dotenv_filtering="match_prefix"` policy by
default. Unrelated namespaces are ignored; extra entries within the application's
prefix follow its `extra` policy. Set `dotenv_filtering="only_existing"` to read
only declared fields. Input aliases, including `AliasChoices` and `AliasPath`,
are normalized before sources are merged, so client keyword overrides retain
their precedence. Cuiman requires Pydantic Settings 2.14.2 or later.

Authentication models require public provider settings, such as `auth.login_url`
for proprietary login or `auth.token_url` for OAuth 2.0. Credentials can be supplied
later through partial overrides or login. Reusing `client.config` keeps a resolved
snapshot; see [configuration reuse](configuration.md#reusing-resolved-configuration).

Define custom `JobResultOpener` subclasses in the application's `opener` module
and list them in `extra_job_result_openers`. This attribute has type
`ClassVar[Iterable[type[JobResultOpener]]]`: its entries are opener classes.
Lists, tuples, and generators are accepted and captured as a tuple at class
creation. Subclasses can assign the attribute without repeating its annotation.
It is excluded from settings and saved profiles.

Each subclass receives a copy of its parent's `return_type_map` and, unless
overridden, its `extra_job_result_openers` at class creation. Declaring a new
iterable replaces the inherited extras; an empty iterable keeps only built-ins.
To extend the parent's declaration, use
`extra_job_result_openers = [*ParentConfig.extra_job_result_openers, MyOpener]`.

Job-result opener registries are cached per concrete class. On first use, they
register the built-ins followed by the declared extras in iteration order. The
last registered opener is tried first, so custom openers take priority over
built-ins. For later changes, use `MyConfig.register_job_result_opener(...)` and
its returned unregister callback. These runtime registrations affect only that
class and are not inherited by subclasses.

## Discovery extensions

Discovery extensions are independent of opener extensions. Declare classes in
`ClientConfig.extra_job_result_resolvers` or register one later using
`MyConfig.register_job_result_resolver(...)`. Later declarations/registrations
take priority over built-in STAC and value discovery. Declarations are captured
as tuples and inherited; runtime registrations are isolated per configuration
class and return an idempotent unregister callback. Resolver classes need a
no-argument constructor. These declarations are excluded from saved settings.

As with openers, `MyConfig.get_job_result_resolver_registry()` returns a registry
cached per concrete configuration class. Its `resolver_types` property is an
ordered tuple snapshot. Developers can construct an empty
`JobResultResolverRegistry` or call `create_default()` to test discovery ordering
independently of client configuration. The registry manages classes; metadata
loaders, budgets, and transformer instances belong to discovery operations.

A project resolver can reuse STAC discovery and own its folder transformation:

```python
from cuiman.api import ClientConfig
from cuiman.api.resolver import (
    ComposedJobResultResolver,
    FolderResourceTransformer,
    ResourceEntry,
)
from cuiman.api.resolver.impl import StacResolver


class ProjectResultResolver(ComposedJobResultResolver):
    def __init__(self):
        # The project supplies configuration; discovery never scans this folder.
        folder = FolderResourceTransformer(
            entries=(
                ResourceEntry(
                    key="reports",
                    location="reports",
                    kind="container",
                    children=(
                        ResourceEntry(
                            key="summary",
                            location="summary.csv",
                            title="Processing summary",
                            media_type="text/csv",
                            roles=("data",),
                        ),
                    ),
                ),
            ),
            matches=lambda resource, ctx: resource.key == "products",
            config_id="project-products",
            config_revision="1",
        )
        super().__init__(
            StacResolver(),
            (folder,),
            accepts=lambda ctx: (
                ctx.process_description is not None
                and ctx.process_description.id == "project-process"
            ),
        )


class ProjectConfig(ClientConfig):
    extra_job_result_resolvers = (ProjectResultResolver,)
```

The base resolver and its transformer share the client's metadata loader and
limits. Acceptance checks project scope and STAC evidence without constructing
the declared subtree. Transformations run after base resolution, preserve
original source descriptions, and attach configuration identity/revision and
relative-path provenance. The folder remains the descendants' ancestor.
Each entry supplies its own format, reader hints, and non-secret access
description; these are not inherited from the folder. Locations support
filesystem paths, file URIs, and hierarchical storage URIs. Relative entries
use the declared folder base even without its trailing separator; absolute
entries retain their supplied locations. Missing configuration or ambiguous
bases produce diagnostics and retain successful siblings.

Selectors use source ancestry and entry keys rather than effective URLs.
Folder location renewal therefore preserves descendant selection. Transformations
are recomputed on each resolution, so refreshed configuration does not reuse a
cached subtree. Completeness describes the configured view, not a verified or
exhaustive directory inventory. Transformation chains are owned by their resolver;
ordinary callers do not configure a separate client-wide pipeline.

These developer contracts are available now. Client listing/traversal and the
resource overload of `open_job_result()` are being integrated in subsequent
steps; the existing client methods do not yet invoke discovery extensions.

## CLI customisation

In a module `src/anolis_client/cli.py`:

```python
import typer
from cuiman.cli import new_cli

from anolis_client import __version__ as version

from anolis_client.api import AnolisClientConfig

cli: typer.Typer = new_cli(
    name="anolis-client",
    summary="Client for the Anolis processing service.",
    version=version,
    config_type=AnolisClientConfig,
)

# As cli is of type `typer.Typer`, you can add custom options here.

if __name__ == "__main__":  # pragma: no cover
    cli()
```

The default CLI loads client configuration, authentication, and notebook
dependencies only when a command needs them. Help and version output do not load
the client runtime. `new_cli()` uses `config_type=None` to defer resolving the
default `ClientConfig`; passing an application configuration class still works
as above. Imports performed by an application's own entry point occur before
`new_cli()` and should also be kept lightweight where possible.

`configure` preserves saved application fields while updating the public API and
authentication settings it edits. It uses profile values and class defaults for
prompts; environment and dotenv overrides are applied when a client is resolved.

## GUI customisation

Please refer to the chapter [GUI-Generation](./gui-generation.md)
dedicated to the generation and customization of the client GUI generated
from OGC process descriptions.
