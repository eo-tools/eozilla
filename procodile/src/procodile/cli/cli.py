#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import json
from typing import TYPE_CHECKING, Annotated, Any, Callable, Optional, Union

import click
import typer

from gavicore.util.cli.group import AliasedGroup
from gavicore.util.cli.parameters import (
    DOT_PATH_OPTION,
    PROCESS_ID_ARGUMENT,
    REQUEST_FILE_OPTION,
    REQUEST_INPUT_OPTION,
    REQUEST_SUBSCRIBER_OPTION,
)

if TYPE_CHECKING:  # pragma: no cover
    from procodile import ProcessRegistry, WorkflowRegistry

PROCESS_REGISTRY_GETTER_KEY = "get_process_registry"

DEFAULT_NAME = "procodile"

DEFAULT_SUMMARY = """`{name}` is a command-line tool to describe and execute
one or more registered processes."""

DEFAULT_HELP = """{summary}

You can use shorter command name aliases, e.g., use command name `ep`
for `execute-process`, or `lp` for `list-processes`.
"""


# noinspection PyShadowingBuiltins
def new_cli(
    registry: Union[str, Union["ProcessRegistry", "WorkflowRegistry"], Callable[[],
    Union["ProcessRegistry", "WorkflowRegistry"]]],
    name: str,
    version: str,
    help: str | None = None,
    summary: str | None = None,
    context: dict[str, Any] | None = None,
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
        name: The name of the CLI application.
        registry: A registry reference string,
            or a registry instance, or a no-arg
            function that returns a registry instance.
        help: Optional CLI application help text. If not provided, the default
            `cuiman` help text will be used.
        summary: A one-sentence human-readable description of the tool that
            will be used by the default help text. Hence, used only,
            if `help` is not provided. Should end with a dot '.'.
        version: Optional version string. If not provided, the
            `cuiman` version will be used.
        context: Additional context values that will be registered with the CLI
            and can be accessed by commands that you add to the
            returned `typer.Typer` instance.

    Return:
        a `typer.Typer` instance
    """
    assert bool(registry), "registry argument must be provided"
    assert bool(name), "name argument must be provided"
    assert bool(version), "version argument must be provided"

    t = typer.Typer(
        cls=AliasedGroup,
        name=name,
        help=(
            help
            or DEFAULT_HELP.format(summary=summary or DEFAULT_SUMMARY.format(name=name))
        ),
        add_completion=False,
        invoke_without_command=True,
        context_settings={
            "obj": {
                PROCESS_REGISTRY_GETTER_KEY: _parse_process_registry_getter(registry),
                **(context or {}),
            },
        },
    )

    @t.callback()
    def main(
        version_: Annotated[
            bool, typer.Option("--version", help="Show version and exit.")
        ] = False,
    ):
        if version_:
            from procodile import __version__ as procodile_version

            typer.echo(f"{version} (procodile {procodile_version})")
            return

    @t.command("execute-process")
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
        settings with the same name found in the given request file or `stdin`,
        if any.
        """
        from procodile import ExecutionRequest, Job

        registry = _get_process_registry(ctx)
        execution_request = ExecutionRequest.create(
            process_id=process_id,
            dotpath=dotpath,
            inputs=request_inputs,
            subscribers=request_subscribers,
            request_path=request_file,
        )
        process_id_ = execution_request.process_id
        process = registry.get(process_id_)
        if process is None:
            raise click.ClickException(f"Process {process_id_!r} not found.")

        job = Job.create(process, request=execution_request.to_process_request())
        job_results = job.run()
        if job_results is not None:
            typer.echo(job_results.model_dump_json(indent=2))
        else:
            typer.echo(job.job_info.model_dump_json(indent=2))

    @t.command("list-processes", help="List all processes.")
    def list_processes(ctx: typer.Context):
        registry = _get_process_registry(ctx)
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
                    for k, v in registry.items()
                },
                indent=2,
            )
        )

    @t.command("get-process", help="Get details of a process.")
    def get_process(
        ctx: typer.Context,
        process_id: Annotated[str, PROCESS_ID_ARGUMENT],
    ):
        import json

        registry = _get_process_registry(ctx)
        process = registry.get(process_id)
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

    return t


__all__ = [
    "new_cli",
]


def _parse_process_registry_getter(
    process_registry: Union[str, Union["ProcessRegistry", "WorkflowRegistry"], Callable[[], Union["ProcessRegistry", "WorkflowRegistry"]]],
) -> Callable[[], Union["ProcessRegistry", "WorkflowRegistry"]]:
    process_registry_getter: Callable
    if isinstance(process_registry, str):

        def process_registry_getter():
            from gavicore.util.dynimp import import_value
            from procodile import ProcessRegistry, WorkflowRegistry

            registry =  import_value(
                process_registry, name="process registry", type=object
            )

            if not isinstance(registry, (ProcessRegistry, WorkflowRegistry)):
                raise TypeError(
                    "The process registry must be a ProcessRegistry or "
                    "WorkflowRegistry, "
                    f"got {type(registry).__name__}."
                )

            return registry

        return process_registry_getter

    elif callable(process_registry):
        return process_registry
    else:

        def process_registry_getter():
            return process_registry

        return process_registry_getter


def _get_process_registry(ctx: typer.Context) -> Union["ProcessRegistry", "WorkflowRegistry"]:
    from procodile import ProcessRegistry, WorkflowRegistry

    process_registry_getter = ctx.obj.get(PROCESS_REGISTRY_GETTER_KEY)
    assert process_registry_getter is not None and callable(process_registry_getter)
    process_registry = process_registry_getter()
    assert isinstance(process_registry, (ProcessRegistry, WorkflowRegistry))
    return process_registry
