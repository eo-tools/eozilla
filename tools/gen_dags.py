#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import importlib
from pathlib import Path
from typing import Any

import typer

from s2gos_common.process import Process
from s2gos_server.services.local import LocalService
from tools.common import S2GOS_PATH, write_file

GENERATOR_NAME = str(Path(__file__).name)

SERVICE_SPEC = "s2gos_server.services.local.testing:service"
DAGS_FOLDER = S2GOS_PATH / "eozilla-airflow/dags"


def main(service_spec: str = SERVICE_SPEC, dags_folder: Path = DAGS_FOLDER):
    service = load_service(service_spec)
    dags_folder.mkdir(exist_ok=True)
    for process_id, process in service.process_registry.items():
        write_file(
            GENERATOR_NAME,
            dags_folder / f"{process_id}.py",
            [gen_dag(process)],
        )


def gen_dag(process: Process) -> str:
    process_description = process.description
    function_name = process_description.id
    input_descriptions = process_description.inputs

    param_specs = [
        f"{param_name!r}: Param({get_param_args(input_description)})"
        for param_name, input_description in input_descriptions.items()
    ]

    tab = "    "
    num_outputs = len(process_description.outputs or [])
    # noinspection PyUnresolvedReferences
    function_module = process.function.__module__
    lines = [
        "from airflow.sdk import Param, dag, task",
        "",
        f"from {function_module} import {function_name}",
        "",
        "",
        "@dag(",
        f"{tab}{function_name!r},",
        f"{tab}dag_display_name={process.description.title!r},",
        f"{tab}description={process_description.description!r},",
        f"{tab}params=" + "{",
        *[f"{tab}{tab}{p}," for p in param_specs],
        f"{tab}" + "},",
        f"{tab}is_paused_upon_creation=False,",
        ")",
        f"def {function_name}_dag():",
        "",
        f"{tab}@task(multiple_outputs={(num_outputs > 1)!r})",
        f"{tab}def {function_name}_task(params):",
        f"{tab}{tab}return {function_name}(**params)",
        "",
        f"{tab}task_instance = {function_name}_task()  # noqa: F841",
        "",
        f"{function_name}_dag()",
    ]
    return "\n".join(lines) + "\n"


def get_param_args(input_description):
    schema = dict(
        input_description.schema_.model_dump(
            mode="json",
            by_alias=True,
            exclude_defaults=True,
            exclude_none=True,
            exclude_unset=True,
        )
    )
    param_args: list[tuple[str, Any]] = []
    if "default" in schema:
        param_args.append(("default", schema.pop("default")))
    if "type" in schema:
        param_args.append(("type", schema.pop("type")))
    if input_description.title:
        schema.pop("title", None)
        param_args.append(("title", input_description.title))
    if input_description.description:
        schema.pop("description", None)
        param_args.append(("description", input_description.description))
    param_args.extend(sorted(schema.items(), key=lambda item: item[0]))
    return ", ".join(f"{sk}={sv!r}" for sk, sv in param_args)


def load_service(service_spec: str) -> LocalService:
    module_name, attr_name = service_spec.rsplit(":", maxsplit=1)
    module = importlib.import_module(module_name)
    service = getattr(module, attr_name)
    assert isinstance(service, LocalService)
    return service


if __name__ == "__main__":
    typer.run(main)
