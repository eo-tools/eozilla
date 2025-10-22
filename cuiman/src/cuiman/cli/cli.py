#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Annotated, Final, Optional

import typer.core

from cuiman.cli.output import OutputFormat
from gavicore.util.cli.group import AliasedGroup
from gavicore.util.cli.parameters import (
    DOT_PATH_OPTION,
    PROCESS_ID_ARGUMENT,
    REQUEST_FILE_OPTION,
    REQUEST_INPUT_OPTION,
    REQUEST_SUBSCRIBER_OPTION,
)


CLI_NAME = "cuiman"
CLI_HELP = """
The command-line interface `{app_name}` is the shell client for servers 
compliant with OGC API - Processes.

The tool can be used to get the available processes, get process details,
execute processes, and manage the jobs originating from the latter. 
It herewith resembles the functionality of the OGC API Processes - Part 1.

You can use shorter command name aliases, e.g., use command name `vr`
for `validate-request`, or `lp` for `list-processes`.

The tool's exit codes are as follows:

- `0` - normal exit
- `1` - user errors, argument errors
- `2` - remote API errors 
- `3` - local network transport errors

If the --traceback flag is set, the original Python exception traceback
will be shown and the exit code will always be `1`. 
Otherwise, only the error message is shown. 
""".format(app_name=CLI_NAME)

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

cli = typer.Typer(
    name=CLI_NAME,
    cls=AliasedGroup,
    help=CLI_HELP,
    invoke_without_command=True,
    context_settings={},
    # rich_markup_mode="rich",  # doesn't work
    # # but should, see https://github.com/fastapi/typer/discussions/818
    # no_args_is_help=True,  # check: it shows empty error msg
)


@cli.callback()
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
        from importlib.metadata import version

        typer.echo(version("cuiman"))
        return

    def get_client(config_path: str | None):
        # defer importing
        from cuiman import Client
        from cuiman.cli.config import get_config

        config = get_config(config_path)
        return Client(config=config)

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


@cli.command()
def configure(
    user_name: Optional[str] = typer.Option(
        None,
        "--user",
        "-u",
        help="Your user name.",
    ),
    access_token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        help="Your personal access token.",
    ),
    server_url: Optional[str] = typer.Option(
        None,
        "--server",
        "-s",
        help="The URL of a service complying to the OGC API - Processes.",
    ),
    config_file: Annotated[Optional[str], CONFIG_OPTION] = None,
):
    """Configure the client tool."""
    from .config import configure_client

    config_path = configure_client(
        user_name=user_name,
        access_token=access_token,
        server_url=server_url,
        config_path=config_file,
    )
    typer.echo(f"Client configuration written to {config_path}")


@cli.command()
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


@cli.command()
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
    output(get_renderer(output_format).render_process_description(process_description))


@cli.command()
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


@cli.command()
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


@cli.command()
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


@cli.command()
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


@cli.command()
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


@cli.command()
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


@cli.command()
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


if __name__ == "__main__":  # pragma: no cover
    cli()
