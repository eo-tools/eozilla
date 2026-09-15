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
    api_url: str | None = "https://anolis.api.org/process-api/v1"
    auth: AuthConfig = NoAuthConfig()
    extra_job_result_openers = [AnolisJobResultsOpener]


def create_client(**config: Any) -> Client:
    return Client(config_type=AnolisClientConfig, **config)


def create_async_client(**config: Any) -> AsyncClient:
    return AsyncClient(config_type=AnolisClientConfig, **config)


cli = new_cli(name="anolis-client", config_type=AnolisClientConfig)
```

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

`configure` preserves saved application fields while updating the public API and
authentication settings it edits. It uses profile values and class defaults for
prompts; environment and dotenv overrides are applied when a client is resolved.

## GUI customisation

Please refer to the chapter [GUI-Generation](./gui-generation.md)
dedicated to the generation and customization of the client GUI generated
from OGC process descriptions.
