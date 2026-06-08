#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from pathlib import Path
from typing import Annotated

import typer

EOZILLA_PATH = Path(__file__).parent.parent.parent.parent.resolve()
DEFAULT_DAGS_FOLDER = EOZILLA_PATH / "eozilla-airflow/dags"
PROCESS_REGISTRY_SPEC_EX = "wraptile.services.local.testing:service.process_registry"
DEFAULT_IMAGE_NAME = "appligator_workflow_image:v1"

CLI_NAME = "appligator"

cli = typer.Typer(name=CLI_NAME)


@cli.command()
def main(
    process_registry_spec: Annotated[
        str | None,
        typer.Argument(
            ...,
            help=f"Process registry specification. For example"
            f" {PROCESS_REGISTRY_SPEC_EX!r}.",
        ),
    ] = None,
    dags_folder: Annotated[
        Path,
        typer.Option(..., help="An Airflow DAGs folder to which to write the outputs."),
    ] = DEFAULT_DAGS_FOLDER,
    image_name: Annotated[
        str | None,
        typer.Option(
            ...,
            help="Name of the Docker image which is created from "
            "your workflow and required packages that Airflow "
            "will use for running the workflows in the registry.",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config-file",
            help="Path to an appligator-config.yaml file. Values from the file "
            "are used as defaults; any flag passed explicitly on the command "
            "line takes precedence.",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(..., help="Show version and exit."),
    ] = False,
    skip_build: Annotated[
        bool,
        typer.Option(
            ..., help="Skip building the Docker image and only generate DAG files."
        ),
    ] = True,
    secret_names: Annotated[
        list[str] | None,
        typer.Option(
            "--secret-name",
            help="Kubernetes secret name to inject as environment variables into every pod "
            "(repeatable, e.g. --secret-name my-secret --secret-name other-secret).",
        ),
    ] = None,
    dag_name: Annotated[
        str | None,
        typer.Option(
            "--dag-name",
            help="Custom name for the generated DAG file (without .py extension). "
            "Defaults to the process ID. If multiple processes are in the registry, "
            "each gets a suffix: <dag-name>_<process_id>.py.",
        ),
    ] = None,
    cpu_request: Annotated[
        str | None,
        typer.Option(
            "--cpu-request", help="CPU request for every pod (e.g. '500m', '1')."
        ),
    ] = None,
    memory_request: Annotated[
        str | None,
        typer.Option(
            "--memory-request",
            help="Memory request for every pod (e.g. '256Mi', '1Gi').",
        ),
    ] = None,
    cpu_limit: Annotated[
        str | None,
        typer.Option("--cpu-limit", help="CPU limit for every pod (e.g. '2')."),
    ] = None,
    memory_limit: Annotated[
        str | None,
        typer.Option("--memory-limit", help="Memory limit for every pod (e.g. '2Gi')."),
    ] = None,
    pvc_mounts: Annotated[
        list[str] | None,
        typer.Option(
            "--pvc-mount",
            help=(
                "Mount a PersistentVolumeClaim into every pod. "
                "Format: name:claim_name:mount_path "
                "(e.g. --pvc-mount output:my-pvc:/mnt/output). Repeatable."
            ),
        ),
    ] = None,
    config_map_mounts: Annotated[
        list[str] | None,
        typer.Option(
            "--config-map-mount",
            help=(
                "Mount a ConfigMap into every pod. "
                "Format: name:config_map_name:mount_path or name:config_map_name:mount_path:sub_path "
                "(e.g. --config-map-mount settings:my-cm:/app/settings.yaml:settings.yaml). Repeatable."
            ),
        ),
    ] = None,
    node_selector: Annotated[
        list[str] | None,
        typer.Option(
            "--node-selector",
            help=(
                "Node selector label for every pod. "
                "Format: key=value (e.g. --node-selector pool=airflow-workers-big). Repeatable."
            ),
        ),
    ] = None,
    tolerations: Annotated[
        list[str] | None,
        typer.Option(
            "--toleration",
            help=(
                "Toleration for every pod. "
                "Format: key:operator[:value[:effect]] "
                "(e.g. --toleration airflow/component:Equal:worker:NoSchedule). Repeatable."
            ),
        ),
    ] = None,
):
    """
    Generate various application formats from your processes.

    WARNING: This tool is under development and subject to change anytime.

    Currently, it expects a _process registry_ as input, which must be
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
    from appligator.airflow.gen_image import gen_image
    from appligator.airflow.gen_workflow_dag import gen_workflow_dag
    from appligator.airflow.models import ConfigMapMount, PvcMount, ResourceRequirements, Toleration
    from appligator.config import AppligatorConfig, load_config
    from gavicore.util.dynimp import import_value
    from procodile import ProcessRegistry

    if version:
        typer.echo(f"{__version__}")
        raise typer.Exit(0)

    if not process_registry_spec:
        typer.echo("Error: missing process registry specification.")
        raise typer.Exit(1)

    # Load config file if provided; CLI flags take precedence over file values.
    cfg = load_config(config_file) if config_file else AppligatorConfig()

    effective_image = image_name or cfg.image_name or DEFAULT_IMAGE_NAME
    effective_dag_name = dag_name or cfg.dag_name
    effective_secrets = (
        secret_names if secret_names is not None else (cfg.secret_names or None)
    )
    effective_cpu_request = cpu_request or cfg.cpu_request
    effective_memory_request = memory_request or cfg.memory_request
    effective_cpu_limit = cpu_limit or cfg.cpu_limit
    effective_memory_limit = memory_limit or cfg.memory_limit

    resources = (
        ResourceRequirements(
            cpu_request=effective_cpu_request,
            memory_request=effective_memory_request,
            cpu_limit=effective_cpu_limit,
            memory_limit=effective_memory_limit,
        )
        if any(
            [
                effective_cpu_request,
                effective_memory_request,
                effective_cpu_limit,
                effective_memory_limit,
            ]
        )
        else None
    )

    # Parse CLI volume specs; fall back to config file if no CLI volumes given.
    parsed_pvc_mounts: list[PvcMount] = []
    for spec in pvc_mounts or []:
        parts = spec.split(":", 2)
        if len(parts) != 3:  # noqa: PLR2004
            typer.echo(
                f"Error: --pvc-mount must be name:claim_name:mount_path, got: {spec!r}"
            )
            raise typer.Exit(1)
        parsed_pvc_mounts.append(
            PvcMount(name=parts[0], claim_name=parts[1], mount_path=parts[2])
        )
    effective_pvc_mounts = (
        parsed_pvc_mounts if pvc_mounts is not None else cfg.pvc_mounts
    )

    parsed_config_map_mounts: list[ConfigMapMount] = []
    for spec in config_map_mounts or []:
        parts = spec.split(":", 3)
        if len(parts) not in (3, 4):
            typer.echo(
                f"Error: --config-map-mount must be name:config_map_name:mount_path[:sub_path], got: {spec!r}"
            )
            raise typer.Exit(1)
        parsed_config_map_mounts.append(
            ConfigMapMount(
                name=parts[0],
                config_map_name=parts[1],
                mount_path=parts[2],
                sub_path=parts[3] if len(parts) == 4 else None,  # noqa: PLR2004
            )
        )
    effective_config_map_mounts = (
        parsed_config_map_mounts
        if config_map_mounts is not None
        else cfg.config_map_mounts
    )

    parsed_node_selector: dict[str, str] = {}
    for spec in node_selector or []:
        if "=" not in spec:
            typer.echo(f"Error: --node-selector must be key=value, got: {spec!r}")
            raise typer.Exit(1)
        k, v = spec.split("=", 1)
        parsed_node_selector[k] = v
    effective_node_selector = (
        parsed_node_selector if node_selector is not None else (cfg.node_selector or None)
    )

    parsed_tolerations: list[Toleration] = []
    for spec in tolerations or []:
        parts = spec.split(":", 3)
        if len(parts) < 2:  # noqa: PLR2004
            typer.echo(
                f"Error: --toleration must be key:operator[:value[:effect]], got: {spec!r}"
            )
            raise typer.Exit(1)
        parsed_tolerations.append(
            Toleration(
                key=parts[0],
                operator=parts[1],
                value=parts[2] if len(parts) > 2 and parts[2] else None,  # noqa: PLR2004
                effect=parts[3] if len(parts) > 3 and parts[3] else None,  # noqa: PLR2004
            )
        )
    effective_tolerations = (
        parsed_tolerations if tolerations is not None else (cfg.tolerations or None)
    )

    process_registry: ProcessRegistry = import_value(
        process_registry_spec,
        type=ProcessRegistry,
        name="process_registry",
        example=PROCESS_REGISTRY_SPEC_EX,
    )

    dags_folder.mkdir(exist_ok=True)

    process_ids = list(process_registry.keys())
    multi = len(process_ids) > 1

    for process_id, _process in process_registry.items():
        if effective_dag_name:
            file_stem = (
                f"{effective_dag_name}_{process_id}" if multi else effective_dag_name
            )
        else:
            file_stem = process_id
        # TODO: implement this better later
        if not skip_build:
            effective_image = gen_image(
                process_registry.get_workflow(process_id).registry,
                image_name=effective_image,
                use_local_packages=True,
            )
        dag_code = gen_workflow_dag(
            dag_id=process_id,
            registry=process_registry.get_workflow(process_id).registry,
            image=effective_image,
            env_from_secrets=effective_secrets,
            resources=resources,
            pvc_mounts=effective_pvc_mounts or None,
            config_map_mounts=effective_config_map_mounts or None,
            node_selector=effective_node_selector or None,
            tolerations=effective_tolerations or None,
        )
        dag_file = dags_folder / f"{file_stem}.py"
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
