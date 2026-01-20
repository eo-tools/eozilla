#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Annotated

import typer

EOZILLA_PATH = Path(__file__).parent.parent.parent.parent.resolve()
DEFAULT_DAGS_FOLDER = EOZILLA_PATH / "eozilla-airflow/dags"
WORKFLOW_REGISTRY_SPEC_EX = "wraptile.services.local.testing:service.workflow_registry"
DEFAULT_IMAGE_NAME = "appligator_workflow_image:v1"

CLI_NAME = "appligator"

cli = typer.Typer(name=CLI_NAME)


@cli.command()
def main(
    workflow_registry_spec: Annotated[
        str | None,
        typer.Argument(
            ...,
            help=f"Workflow registry specification. For example"
            f" {WORKFLOW_REGISTRY_SPEC_EX!r}.",
        ),
    ] = None,
    dags_folder: Annotated[
        Path,
        typer.Option(..., help="An Airflow DAGs folder to which to write the outputs."),
    ] = DEFAULT_DAGS_FOLDER,
    image_name: Annotated[
        str,
        typer.Option(
            ...,
            help="Name of the Docker image which is created from "
            "your workflow and required packages that Airflow "
            "will use for running the workflows in the registry.",
        ),
    ] = DEFAULT_IMAGE_NAME,
    version: Annotated[
        bool,
        typer.Option(..., help="Show version and exit."),
    ] = False,
):
    """
    Generate various application formats from your processing workflows.

    WARNING: This tool is under development and subject to change anytime.

    Currently, it expects a _workflow registry_ as input, which must be
    provided in form a Python module path plus an attribute path separated
    by a colon: "my.module.path:my.registry_obj". The type of the registry
    must be `procodile.WorkflowRegistry`. In the future the tool will be
    able to handle other input types.

    It is also currently limited to generating DAGs for Airflow 3+.
    The plan is to extend it to also output Docker images with or
    without metadata such as the OGC CWL standard (= EOAP).
    """
    import datetime

    from appligator import __version__
    from appligator.airflow.gen_image import gen_image
    from appligator.airflow.gen_workflow_dag import gen_workflow_dag
    from gavicore.util.dynimp import import_value
    from procodile import WorkflowRegistry

    if version:
        typer.echo(f"{__version__}")
        raise typer.Exit(0)

    if not workflow_registry_spec:
        typer.echo("Error: missing process registry specification.")
        raise typer.Exit(1)

    registry: WorkflowRegistry = import_value(
        workflow_registry_spec,
        type=WorkflowRegistry,
        name="workflow_registry",
        example=WORKFLOW_REGISTRY_SPEC_EX,
    )

    dags_folder.mkdir(exist_ok=True)

    for process_id, process in registry.items():
        # TODO: implement this better later
        image_name = gen_image(
            registry.get_workflow(process_id).registry,
            image_name=image_name,
            use_local_packages=True,
        )
        dag_code = gen_workflow_dag(
            dag_id=process_id,
            registry=registry.get_workflow(process_id).registry,
            image=image_name,
        )
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
