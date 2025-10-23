#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Any

from gavicore.models import InputDescription, ProcessDescription
from procodile import Process


def gen_dag(process: Process | ProcessDescription, function_module: str = "") -> str:
    if isinstance(process, Process):
        process_description = process.description
        # noinspection PyUnresolvedReferences
        function_module = function_module or process.function.__module__
    elif isinstance(process, ProcessDescription):
        process_description = process
        if not function_module:
            raise ValueError("function_module argument is required")
    else:
        raise TypeError(f"unexpected type for process: {type(process).__name__}")

    return _gen_dag(process_description, function_module)


def _gen_dag(process_description: ProcessDescription, function_module: str) -> str:
    function_name = process_description.id
    input_descriptions = process_description.inputs or {}

    param_specs = [
        f"{param_name!r}: Param({get_param_args(input_description)})"
        for param_name, input_description in input_descriptions.items()
    ]

    tab = "    "
    num_outputs = len(process_description.outputs or [])
    lines = [
        "from airflow.sdk import Param, dag, task",
        "",
        f"from {function_module} import {function_name}",
        "",
        "",
        "@dag(",
        f"{tab}{function_name!r},",
        f"{tab}dag_display_name={process_description.title!r},",
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


def get_param_args(input_description: InputDescription):
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
