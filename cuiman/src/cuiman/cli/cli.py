#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Final, Optional

import click
import typer.core

from cuiman.api.auth import AuthType
from cuiman.api.auth.config import AUTH_TYPE_NAMES
from cuiman.cli.output import OutputFormat
from gavicore.util.cli.group import AliasedGroup
from gavicore.util.cli.parameters import (
    DOT_PATH_OPTION,
    PROCESS_ID_ARGUMENT,
    REQUEST_FILE_OPTION,
    REQUEST_INPUT_OPTION,
    REQUEST_SUBSCRIBER_OPTION,
)

DEFAULT_NAME = "cuiman"

DEFAULT_SUMMARY = """The `{name}` tool is a shell client for any web services 
compliant with OGC API - Processes, Part 1: Core Standard.
"""

DEFAULT_HELP = """{summary}

`{name}` can be used to get the available processes, get process 
details, execute processes, and manage the jobs originating from the latter. It 
herewith resembles the core functionality of the OGC API - Processes, Part 1.
For details see https://ogcapi.ogc.org/processes/.

You can use shorter command name aliases, e.g., use command name `vr`
for `validate-request`, or `lp` for `list-processes`.

The tool's exit codes are as follows:

* `0` - normal exit
* `1` - user errors, argument errors
* `2` - remote API errors 
* `3` - local network transport errors

If the `--traceback` flag is set, the original Python exception traceback
will be shown and the exit code will always be `1`. 
Otherwise, only the error message is shown. 
"""

DEFAULT_OUTPUT_FORMAT: Final = OutputFormat.yaml

CONFIG_OPTION = typer.Option(
    "--config",
    "-c",
    help="Client configuration file.",
    metavar="PATH",
)

FORMAT_OPTION = typer.Option(
    ...,
    "--format",
    "-f",
    show_choices=True,
    help="Output format.",
    # metavar="FORMAT",
)

JOB_ID_ARGUMENT = typer.Argument(
    help="Job identifier.",
)


# noinspection PyShadowingBuiltins
def new_cli(
    name: str = DEFAULT_NAME,
    help: str | None = None,
    summary: str | None = None,
    version: str | None = None,
    auth_strategy: AuthType | None = None,
) -> typer.Typer:
    """
    Create a server CLI instance for the given, optional name and help text.

    Args:
        name: The name of the CLI application. Defaults to `wraptile`.
        help: Optional CLI application help text. If not provided, the default
            `cuiman` help text will be used.
        summary: A one-sentence human-readable description of the tool that
            will be used by the default help text. Hence, used only,
            if `help` is not provided. Should end with a dot '.'.
        version: Optional version string. If not provided, the
            `cuiman` version will be used.
        auth_strategy: Optional client authentication strategy.
            Defaults to no-authentication (`AuthStrategy.NONE`).
    Return:
        a `typer.Typer` instance
    """
    t = typer.Typer(
        name=name,
        cls=AliasedGroup,
        help=(
            help
            or DEFAULT_HELP.format(
                name=name,
                summary=(summary or DEFAULT_SUMMARY.format(name=name)),
            )
        ),
        invoke_without_command=True,
        context_settings={},
        rich_markup_mode="rich",
        # no_args_is_help=True,  # check: it shows empty error msg
    )

    @t.callback()
    def main(
        ctx: typer.Context,
        version_: Annotated[
            bool, typer.Option("--version", help="Show version and exit.")
        ] = False,
        traceback: Annotated[
            bool,
            typer.Option(
                "--traceback", "--tb", help="Show server exception traceback, if any."
            ),
        ] = False,
        # add global options here...
        # verbose: bool = typer.Option(False, "--verbose", "-v",
        #                              help="Verbose output"),
    ):
        if version_:
            from cuiman import __version__ as default_version

            if version:
                typer.echo(f"{version} ({DEFAULT_NAME} {default_version})")
            else:
                typer.echo(default_version)
            return

        def get_client(config_path: str | None):
            # defer importing
            from cuiman import Client
            from cuiman.cli.config import get_config

            config = get_config(config_path)
            # "pragma: no cover" is here because coverage reports
            # the next line as uncovered, but that's definitely no true.
            return Client(config=config)  # pragma: no cover

        ctx.ensure_object(dict)
        # ONLY set context values if they haven't already been set,
        # for example, by a test
        for k, v in dict(
            get_client=get_client,
            traceback=traceback,
            # add global options here...
            # verbose=verbose,
        ).items():
            if k not in ctx.obj:
                ctx.obj[k] = v

    @t.command()
    def configure(
        api_url: Annotated[
            str | None,
            typer.Option(
                "--api-url",
                help="The URL of a service complying to the OGC API - Processes.",
            ),
        ] = None,
        auth_type: Annotated[
            str | None,
            typer.Option(
                "--auth-type",
                "-a",
                help="The authorisation method for the API "
                f"({'|'.join(AUTH_TYPE_NAMES)}).",
            ),
        ] = None,
        auth_url: Annotated[
            str | None,
            typer.Option(
                "--auth-url",
                help="The URL of the authorisation service for the API ",
            ),
        ] = None,
        username: Annotated[
            str | None,
            typer.Option(
                "--username",
                "-u",
                help="Username.",
            ),
        ] = None,
        password: Annotated[
            str | None,
            typer.Option(
                "--password",
                "-p",
                help="Password.",
            ),
        ] = None,
        token: Annotated[
            str | None,
            typer.Option(
                "--token",
                "-t",
                help="Access token.",
            ),
        ] = None,
        use_bearer: Annotated[
            bool | None,
            typer.Option(
                "--use-bearer",
                help="Use bearer token?",
            ),
        ] = None,
        token_header: Annotated[
            str | None,
            typer.Option(
                "--token-header",
                help="Access token header",
            ),
        ] = None,
        config_file: Annotated[str | None, CONFIG_OPTION] = None,
    ):
        """Configure the client tool."""
        from .config import configure_client_with_prompt

        if auth_type is not None and auth_type not in AUTH_TYPE_NAMES:
            raise click.ClickException(f"Invalid authentication type: {auth_type}")

        config_path = configure_client_with_prompt(
            config_path=config_file,
            api_url=api_url,
            auth_type=auth_type,  # type: ignore[arg-type]
            auth_url=auth_url,
            username=username,
            password=password,
            token=token,
            use_bearer=use_bearer,
            token_header=token_header,
        )
        typer.echo(f"Client configuration written to {config_path}")

    @t.command()
    def list_processes(
        ctx: typer.Context,
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """List available processes."""
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            process_list = client.get_processes()
        output(get_renderer(output_format).render_process_list(process_list))

    @t.command()
    def get_process(
        ctx: typer.Context,
        process_id: Annotated[str, PROCESS_ID_ARGUMENT],
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """Get process details."""
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            process_description = client.get_process(process_id)
        output(
            get_renderer(output_format).render_process_description(process_description)
        )

    @t.command()
    def create_request(
        ctx: typer.Context,
        process_id: Annotated[Optional[str], PROCESS_ID_ARGUMENT] = None,
        dotpath: Annotated[bool, DOT_PATH_OPTION] = False,
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """
        Create an execution request (template) for a given process.

        The generated template comprises generated default values for all inputs.
        Note that they might not necessarily be valid.
        The generated template request may serve as a starting point for the actual,
        valid execution request.
        """
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            request = client.create_execution_request(process_id, dotpath=dotpath)

        output(get_renderer(output_format).render_execution_request_valid(request))

    @t.command()
    def validate_request(
        process_id: Annotated[Optional[str], PROCESS_ID_ARGUMENT] = None,
        dotpath: Annotated[bool, DOT_PATH_OPTION] = False,
        request_inputs: Annotated[Optional[list[str]], REQUEST_INPUT_OPTION] = None,
        request_file: Annotated[Optional[str], REQUEST_FILE_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """
        Validate a process execution request.

        The execution request to be validated may be read from a file given
        by `--request`, or from `stdin`, or from the `process_id` argument
        with zero, one, or more `--input` (or `-i`) options.

        The `process_id` argument and any given `--input` options will override
        settings with the same name found in the given request file or `stdin`, if any.
        """
        from gavicore.util.request import ExecutionRequest

        from .output import get_renderer, output

        request = ExecutionRequest.create(
            process_id=process_id,
            dotpath=dotpath,
            inputs=request_inputs,
            request_path=request_file,
        )
        output(get_renderer(output_format).render_execution_request_valid(request))

    @t.command()
    def execute_process(
        ctx: typer.Context,
        process_id: Annotated[Optional[str], PROCESS_ID_ARGUMENT] = None,
        dotpath: Annotated[bool, DOT_PATH_OPTION] = False,
        request_inputs: Annotated[Optional[list[str]], REQUEST_INPUT_OPTION] = None,
        request_subscribers: Annotated[
            Optional[list[str]], REQUEST_SUBSCRIBER_OPTION
        ] = None,
        request_file: Annotated[Optional[str], REQUEST_FILE_OPTION] = None,
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """
        Execute a process in asynchronous mode.

        The execution request to be submitted may be read from a file given
        by `--request`, or from `stdin`, or from the `process_id` argument
        with zero, one, or more `--input` (or `-i`) options.

        The `process_id` argument and any given `--input` options will override
        settings with same name found in the given request file or `stdin`, if any.
        """
        from gavicore.util.request import ExecutionRequest

        from .client import use_client
        from .output import get_renderer, output

        request = ExecutionRequest.create(
            process_id=process_id,
            dotpath=dotpath,
            inputs=request_inputs,
            subscribers=request_subscribers,
            request_path=request_file,
        )
        with use_client(ctx, config_file) as client:
            job = client.execute_process(
                process_id=request.process_id, request=request.to_process_request()
            )
        output(get_renderer(output_format).render_job_info(job))

    @t.command()
    def list_jobs(
        ctx: typer.Context,
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """List all jobs."""
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            job_list = client.get_jobs()
        output(get_renderer(output_format).render_job_list(job_list))

    @t.command()
    def get_job(
        ctx: typer.Context,
        job_id: Annotated[str, JOB_ID_ARGUMENT],
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """Get job details."""
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            job = client.get_job(job_id)
        output(get_renderer(output_format).render_job_info(job))

    @t.command()
    def dismiss_job(
        ctx: typer.Context,
        job_id: Annotated[str, JOB_ID_ARGUMENT],
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """Cancel a running or delete a finished job."""
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            job = client.dismiss_job(job_id)
        output(get_renderer(output_format).render_job_info(job))

    @t.command()
    def get_job_results(
        ctx: typer.Context,
        job_id: Annotated[str, JOB_ID_ARGUMENT],
        config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
        output_format: Annotated[OutputFormat, FORMAT_OPTION] = DEFAULT_OUTPUT_FORMAT,
    ):
        """Get job results."""
        from .client import use_client
        from .output import get_renderer, output

        with use_client(ctx, config_file) as client:
            job_results = client.get_job_results(job_id)
        output(get_renderer(output_format).render_job_results(job_results))

    return t


cli: typer.Typer = new_cli()
"""The default CLI instance."""

if __name__ == "__main__":  # pragma: no cover
    cli()
