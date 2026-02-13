# Wraptile Customization

Applications can create their own servers using `wraptile` under the hood. 
For this, an application can customize the `wraptile` configuration and its
default values.

This is best explained by an example. In the following we explain 
the client customization by a hypothetic processing system "Anolis"
that should get its own `anolis-server`.

The `wraptile` API currently just allows for customizing the CLI:

## CLI customisation

In a module `src/anolis_server/cli.py`:

```python
from wraptile.cli import new_cli
from anolis_server import __version__ as version

cli = new_cli(
    name="anolis-server", 
    summary="Server providing the Anolis processing service.",
    version=version
)

__all__ = ["cli"]

if __name__ == "__main__":  # pragma: no cover
    cli()    
```
