# Client Customization

Applications can create their own clients using `cuiman` under the hood. 
For this, an application can customize the `cuiman` configuration and its
default values.

This is best explained by an example. In the following we explain 
the client customization by a hypothetic processing system "Anolis"
that should get its own `anolis-client`.

The `cuiman` API allows for the following customizations:

1. The `cuiman.ClientConfig` is a 
   [pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
   class. It can be used as base class and then configured with a custom 
   `pydantic_settings.SettingsConfigDict` instance.
2. Some `cuiman.ClientConfig` class attributes in can be overridden     
   to initialize custom default values.
3. Applications can create their own CLI instance with custom settings.


## API customisation

In a module `src/anolis_client/api.py`:

```python
from pathlib import Path
from pydantic_settings import SettingsConfigDict
from cuiman.api import AsyncClient, Client, ClientConfig, ClientError

# Custom configuration class
class AnolisClientConfig(ClientConfig):
  model_config = SettingsConfigDict(
      env_prefix="ANOLIS_",
      env_file=".env",
      extra="allow",  # base ClientConfig uses "forbid"
  )

# Custom configuration defaults
ClientConfig.default_path = Path("~").expanduser() / ".anolis-client"
ClientConfig.default_config = AnolisClientConfig(
    api_url="https://anolis.api.org/process-api/v1",
    auth_url="https://anolis.api.org/auth/login",
    auth_type="login",
    use_bearer=True,
)
```

## CLI customisation

In a module `src/anolis_client/cli.py`:

```python
from importlib import import_module
from cuiman.cli import new_cli
from anolis_client import __version__ as version

# Force pre-configuration of Anolis configuration
import_module("anolis_client.api")

cli = new_cli(
    name="anolis-client",
    summary="Client for the Anolis processing service.",
    version=version,
)

if __name__ == "__main__":  # pragma: no cover
    cli()
```
