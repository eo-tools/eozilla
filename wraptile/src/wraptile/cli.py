#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import logging
from typing import Annotated, Optional

import typer

from wraptile.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENV_VAR_SERVER_HOST,
    ENV_VAR_SERVER_PORT,
    ENV_VAR_SERVICE,
)
from wraptile.logging import LogMessageFilter

DEFAULT_CLI_NAME = "wraptile"
DEFAULT_CLI_HELP_TEMPLATE = """
`{cli_name}` is a web server made for wrapping workflow orchestration 
systems with a unified restful API that should be almost compliant
with the OGC API - Processes - Part 1: Core Standard.

For details see https://ogcapi.ogc.org/processes/.

The service instance may be followed by a `--` to pass one or more 
service-specific arguments and options.

Note that the service arguments may also be given by the 
environment variable `{service_env_var}`.
"""


def parse_cli_service_options(
    _ctx: typer.Context, kwargs: Optional[list[str]] = None
) -> list[str]:
    import os
    import shlex

    if not kwargs:
        return []
    service_args = os.environ.get(ENV_VAR_SERVICE)
    if kwargs == [service_args]:
        return shlex.split(service_args)
    return kwargs


CLI_HOST_OPTION = typer.Option(
    envvar=ENV_VAR_SERVER_HOST,
    help="Host address.",
)
CLI_PORT_OPTION = typer.Option(
    envvar=ENV_VAR_SERVER_PORT,
    help="Port number.",
)
CLI_SERVICE_ARG = typer.Argument(
    callback=parse_cli_service_options,
    envvar=ENV_VAR_SERVICE,
    help=(
        "Service instance optionally followed by `--` to pass "
        "service-specific arguments and options. SERVICE should "
        "have the form `path.to.module:service`."
    ),
    metavar="SERVICE [-- SERVICE-OPTIONS]",
)


# noinspection PyShadowingBuiltins
def get_cli(name: str = DEFAULT_CLI_NAME, help: str | None = None) -> typer.Typer:
    """
    Create a server CLI instance for the given, optional name and help text.

    Args:
        name: The name of the CLI application. Defaults to `wraptile`.
        help: Optional CLI application help text. If not provided, a default help
            text will be used
    Return:
        a `typer.Typer` instance
    """
    t = typer.Typer(
        name=name,
        help=(
            help
            or DEFAULT_CLI_HELP_TEMPLATE.format(
                cli_name=name, service_env_var=ENV_VAR_SERVICE
            )
        ),
        invoke_without_command=True,
    )

    @t.callback()
    def main(
        _ctx: typer.Context,
        version_: Annotated[
            bool, typer.Option("--version", help="Show version and exit.")
        ] = False,
    ):
        if version_:
            from importlib.metadata import version

            typer.echo(version("wraptile"))
            raise typer.Exit()

    @t.command()
    def run(
        host: Annotated[str, CLI_HOST_OPTION] = DEFAULT_HOST,
        port: Annotated[int, CLI_PORT_OPTION] = DEFAULT_PORT,
        service: Annotated[Optional[list[str]], CLI_SERVICE_ARG] = None,
    ):
        """Run server in production mode."""
        _run_server(
            host=host,
            port=port,
            service=service,
            reload=False,
        )

    @t.command()
    def dev(
        host: Annotated[str, CLI_HOST_OPTION] = DEFAULT_HOST,
        port: Annotated[int, CLI_PORT_OPTION] = DEFAULT_PORT,
        service: Annotated[Optional[list[str]], CLI_SERVICE_ARG] = None,
    ):
        """Run server in development mode."""
        _run_server(
            host=host,
            port=port,
            service=service,
            reload=True,
        )

    return t


def _run_server(**kwargs):
    import os
    import shlex

    import uvicorn

    service = kwargs.pop("service", None)
    if isinstance(service, list) and service:
        os.environ[ENV_VAR_SERVICE] = shlex.join(service)

    # Apply the filter to the uvicorn.access logger
    logging.getLogger("uvicorn.access").addFilter(LogMessageFilter("/jobs"))

    uvicorn.run("wraptile.main:app", **kwargs)


cli: typer.Typer = get_cli()
"""The default CLI instance."""

if __name__ == "__main__":  # pragma: no cover
    cli()
