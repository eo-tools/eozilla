#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from typing import TYPE_CHECKING, Annotated, Callable, Optional, Union

import click
import typer

from s2gos_common.util.cli.group import AliasedGroup
from s2gos_common.util.cli.parameters import (
    DOT_PATH_OPTION,
    PROCESS_ID_ARGUMENT,
    REQUEST_FILE_OPTION,
    REQUEST_INPUT_OPTION,
    REQUEST_SUBSCRIBER_OPTION,
)

if TYPE_CHECKING:  # pragma: no cover
    from s2gos_common.process import ProcessRegistry


PROCESS_REGISTRY_GETTER_KEY = "get_process_registry"

CLI_HELP = """Command-line interface for process description and execution.

You can use shorter command name aliases, e.g., use command name `ep`
for `execute-process`, or `lp` for `list-processes`.
"""

cli = typer.Typer(
    add_completion=False,
    cls=AliasedGroup,
    help=CLI_HELP,
    context_settings={
        "obj": {PROCESS_REGISTRY_GETTER_KEY: None},
    },
)


def get_cli(
    process_registry: Union[str, "ProcessRegistry", Callable[[], "ProcessRegistry"]],
    **kwargs,
) -> typer.Typer:
    """
    Get the CLI instance configured to use the process registry
    that is given either by

    - a reference of the form "path.to.module:attribute",
    - or process registry instance,
    - or as a no-arg process registry getter function.

    The process registry is usually a singleton in your application.

    The context object `obj` of the returned CLI object
    will be of type `dict` and will contain
    a process registry getter function using the key
    `get_process_registry`.

    The function must be called before any CLI command or
    callback has been invoked. Otherwise, the provided
    `get_process_registry` getter will not be recognized and
    all commands that require the process registry will
    fail with an `AssertionError`.

    Args:
        process_registry: A registry reference string,
            or a registry instance, or a no-arg
            function that returns a registry instance.
        kwargs: Additional context values that will be registered in the

    """
    if isinstance(process_registry, str):

        def get_process_registry():
            from s2gos_common.process import ProcessRegistry
            from s2gos_common.util.dynimp import import_value

            return import_value(
                process_registry, name="process registry", type=ProcessRegistry
            )

        return get_cli(get_process_registry)

    elif not callable(process_registry):
        return get_cli(lambda: process_registry)

    assert callable(process_registry)
    context_settings = cli.info.context_settings
    assert isinstance(context_settings, dict)
    context_obj = context_settings["obj"]
    assert isinstance(context_obj, dict)
    context_obj.update({PROCESS_REGISTRY_GETTER_KEY: process_registry, **kwargs})
    return cli


__all__ = [
    "get_cli",
]


@cli.command("execute-process")
def execute_process(
    ctx: typer.Context,
    process_id: Annotated[Optional[str], PROCESS_ID_ARGUMENT] = None,
    dotpath: Annotated[bool, DOT_PATH_OPTION] = False,
    request_inputs: Annotated[Optional[list[str]], REQUEST_INPUT_OPTION] = None,
    request_subscribers: Annotated[
        Optional[list[str]], REQUEST_SUBSCRIBER_OPTION
    ] = None,
    request_file: Annotated[Optional[str], REQUEST_FILE_OPTION] = None,
):
    """
    Execute a process.

    The process request to be submitted may be read from a file given
    by `--request`, or from `stdin`, or from the `process_id` argument
    with zero, one, or more `--input` (or `-i`) options.

    The `process_id` argument and any given `--input` options will override
    settings with same name found in the given request file or `stdin`, if any.
    """
    from s2gos_common.process import Job
    from s2gos_common.process.request import ExecutionRequest

    process_registry = _get_process_registry(ctx)
    execution_request = ExecutionRequest.create(
        process_id=process_id,
        dotpath=dotpath,
        inputs=request_inputs,
        subscribers=request_subscribers,
        request_path=request_file,
    )
    process_id_ = execution_request.process_id
    process = process_registry.get(process_id_)
    if process is None:
        raise click.ClickException(f"Process {process_id_!r} not found.")

    job = Job.create(process, request=execution_request.to_process_request())
    job_results = job.run()
    if job_results is not None:
        typer.echo(job_results.model_dump_json(indent=2))
    else:
        typer.echo(job.job_info.model_dump_json(indent=2))


@cli.command("list-processes", help="List all processes.")
def list_processes(ctx: typer.Context):
    process_registry = _get_process_registry(ctx)
    typer.echo(
        json.dumps(
            {
                k: v.description.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                    exclude_defaults=True,
                    exclude_unset=True,
                    exclude={"inputs", "outputs"},
                )
                for k, v in process_registry.items()
            },
            indent=2,
        )
    )


@cli.command("get-process", help="Get details of a process.")
def get_process(
    ctx: typer.Context,
    process_id: Annotated[str, PROCESS_ID_ARGUMENT],
):
    import json

    process_registry = _get_process_registry(ctx)
    process = process_registry.get(process_id)
    if process is None:
        raise click.ClickException(f"Process {process_id!r} not found.")

    typer.echo(
        json.dumps(
            process.description.model_dump(
                mode="json",
                by_alias=True,
                exclude_defaults=True,
                exclude_none=True,
                exclude_unset=True,
            ),
            indent=2,
        )
    )


def _get_process_registry(ctx: typer.Context) -> "ProcessRegistry":
    from s2gos_common.process import ProcessRegistry

    process_registry_getter = ctx.obj.get(PROCESS_REGISTRY_GETTER_KEY)
    assert process_registry_getter is not None and callable(process_registry_getter)
    process_registry = process_registry_getter()
    assert isinstance(process_registry, ProcessRegistry)
    return process_registry
