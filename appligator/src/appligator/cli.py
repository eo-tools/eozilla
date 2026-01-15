#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Annotated

import typer

from appligator.airflow.gen_image import gen_image
from appligator.airflow.gen_workflow_dag import gen_workflow_dag
from procodile import WorkflowRegistry

EOZILLA_PATH = Path(__file__).parent.parent.parent.parent.resolve()
DEFAULT_DAGS_FOLDER = EOZILLA_PATH / "eozilla-airflow/dags"
PROCESS_REGISTRY_SPEC_EX = (
    "wraptile.services.local.testing_process:service.process_registry"
)

CLI_NAME = "appligator"

cli = typer.Typer(name=CLI_NAME)


@cli.command()
def main(
    process_or_workflow_registry_spec: Annotated[
        str | None,
        typer.Argument(
            ...,
            help=f"Process or Workflow registry specification. For example "
                 f"{PROCESS_REGISTRY_SPEC_EX!r}.",
        ),
    ] = None,
    dags_folder: Annotated[
        Path,
        typer.Option(..., help="An Airflow DAGs folder to which to write the outputs."),
    ] = DEFAULT_DAGS_FOLDER,
    version: Annotated[
        bool,
        typer.Option(..., help="Show version and exit."),
    ] = False,
):
    """
    Generate various application formats from your processing workflows.

    WARNING: This tool is under development and subject to change anytime.

    Currently it expects a _process registry_ as input, which must be
    provided in form a Python module path plus an attribute path separated
    by a colon: "my.module.path:my.registry_obj". The type of the registry
    must be `procodile.ProcessRegistry`. In the future the tool will be
    able to handle other input types.

    It is also currently limited to generating DAGs for Airflow 3+.
    The plan is to extend it to also output Docker images with or
    without metadata such as the OGC CWL standard (= EOAP).
    """
    import datetime

    from appligator import __version__
    from appligator.airflow.gen_dag import gen_dag
    from gavicore.util.dynimp import import_value
    from procodile import ProcessRegistry

    if version:
        typer.echo(f"{__version__}")
        raise typer.Exit(0)

    if not process_or_workflow_registry_spec:
        typer.echo("Error: missing process/workflow registry specification.")
        raise typer.Exit(1)

    # process_registry: ProcessRegistry = import_value(
    #     process_registry_spec,
    #     type=ProcessRegistry,
    #     name="process_registry",
    #     example=PROCESS_REGISTRY_SPEC_EX,
    # )
    try:
        registry = import_value(
            process_or_workflow_registry_spec,
            type=ProcessRegistry,
            name="process_registry",
            example=PROCESS_REGISTRY_SPEC_EX,
        )
        kind = "process"
    except TypeError:
        try:
            registry = import_value(
                process_or_workflow_registry_spec,
                type=WorkflowRegistry,
                name="workflow_registry",
                example=PROCESS_REGISTRY_SPEC_EX,
            )
            kind = "workflow"
        except TypeError:
            typer.echo("Registry must be either ProcessRegistry or WorkflowRegistry")
            raise typer.Exit(1)

    dags_folder.mkdir(exist_ok=True)

    if kind=="process":
        typer.echo(f"genning dag now {dags_folder}")
        for process_id, process in registry.items():
            dag_code = gen_dag(process)
            typer.echo(f"{dag_code}")
            dag_file = dags_folder / f"{process_id}.py"
            with dag_file.open("w") as stream:
                stream.write(
                    f"# WARNING - THIS IS GENERATED CODE\n"
                    f"#   Generator: Eozilla Appligator v{__version__}\n"
                    f"#        Date: {datetime.datetime.now().isoformat()}\n"
                    f"\n"
                    f"{dag_code}"
                )
    else:
        for process_id, process in registry.items():
            image_name = gen_image(registry.get_workflow(process_id).registry,
                      image_name="test_gen_image:v2", use_local_packages=True)
            dag_code = gen_workflow_dag(dag_id=process_id,
                                        registry=registry.get_workflow(
                                            process_id).registry, image=image_name, output_dir=dags_folder)
            dag_file = dags_folder / f"{process_id}.py"
            with dag_file.open("w") as stream:
                stream.write(
                    f"# WARNING - THIS IS GENERATED CODE\n"
                    f"#   Generator: Eozilla Appligator v{__version__}\n"
                    f"#        Date: {datetime.datetime.now().isoformat()}\n"
                    f"\n"
                    f"{dag_code}"
                )


if __name__ == "__main__":  # pragma: no cover
    cli()
