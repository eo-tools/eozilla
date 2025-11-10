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

DEFAULT_NAME = "wraptile"

DEFAULT_SUMMARY = """`{name}` is a web server made for wrapping workflow 
orchestration systems providing an API compliant with the OGC API - Processes,
Part 1: Core Standard (https://ogcapi.ogc.org/processes/).
"""

DEFAULT_HELP = """{summary}

The SERVICE argument may be followed by a `--` to pass one or more 
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
def new_cli(
    name: str = DEFAULT_NAME,
    /,
    help: str | None = None,
    summary: str | None = None,
    version: str | None = None,
) -> typer.Typer:
    """
    Create a server CLI instance for the given, optional name and help text.

    Args:
        name: The name of the CLI application. Defaults to `wraptile`.
        help: Optional CLI application help text. If not provided, the default
            `wraptile` help text will be used
        summary: A one-sentence human-readable description of the tool that
            will be used by the default help text. Hence, used only,
            if `help`is not provided. Should end with a dot '.'.
        version: Optional version string. If not provided, the
            `wraptile` version will be used.
    Return:
        a `typer.Typer` instance
    """
    t = typer.Typer(
        name=name,
        help=(
            help
            or DEFAULT_HELP.format(
                name=name,
                summary=(summary or DEFAULT_SUMMARY.format(name=name)),
                service_env_var=ENV_VAR_SERVICE,
            )
        ),
        rich_markup_mode="rich",
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
            from wraptile import __version__ as default_version

            if version:
                typer.echo(f"{version} ({DEFAULT_NAME} {default_version})")
            else:
                typer.echo(default_version)
            return

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

    # noinspection PyArgumentList
    uvicorn.run("wraptile.main:app", **kwargs)


cli: typer.Typer = new_cli()
"""The default CLI instance."""

__all__ = [
    "cli",
    "new_cli",
]

if __name__ == "__main__":  # pragma: no cover
    cli()
