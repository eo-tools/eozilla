#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from procodile.cli import new_cli

from procodile_example import __version__

# The CLI with a basic set of commands.
# The `cli` is a Typer application of type `typer.Typer()`,
# so can use the instance to register your own commands.
cli = new_cli(
    registry="procodile_example.processes:registry",
    name="procodile-example",
    version=__version__,
)


__all__ = ["cli"]
