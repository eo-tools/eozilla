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

Set a complete nested `auth` configuration through a configuration file or
environment variables. Authentication models require their credentials at
construction time; for example, a proprietary login uses `auth.login_url`,
while OAuth 2.0 uses `auth.token_url`.

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

## GUI customisation

Please refer to the chapter [GUI-Generation](./gui-generation.md)
dedicated to the generation and customization of the client GUI generated
from OGC process descriptions.
