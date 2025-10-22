#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
import re
from pathlib import Path
from typing import Literal

from tools.common import (
    C_TAB,
    OPEN_API_PATH,
    S2GOS_PATH,
    camel_to_snake,
    parse_responses,
    to_py_type,
    write_file,
)
from tools.openapi import OAMethod, OASchema, load_openapi_schema

GENERATOR_NAME = str(Path(__file__).name)

ROUTES_PATH = S2GOS_PATH / "wraptile/src/s2gos_server/routes.py"
SERVICE_PATH = S2GOS_PATH / "gavicore/src/gavicore/service.py"

magic_param_list = [
    ("request", "fastapi.Request"),
    ("response", "fastapi.Response"),
    # add more as desired
]


def main():
    schema = load_openapi_schema(OPEN_API_PATH)
    models: set[str] = set()
    routes_code, service_code = generate_code_for_paths(schema, models)
    model_list = ", ".join(sorted(models))

    write_file(
        GENERATOR_NAME,
        ROUTES_PATH,
        [
            "import fastapi\n",
            "\n",
            f"from gavicore.models import {model_list}\n",
            "from gavicore.service import Service\n",
            "from .app import app\n",
            "from .provider import get_service\n",
            "\n",
            routes_code,
        ],
    )

    write_file(
        GENERATOR_NAME,
        SERVICE_PATH,
        [
            "from abc import ABC, abstractmethod\n",
            "\n",
            f"from .models import {model_list}\n",
            "\n",
            "class Service(ABC):\n",
            service_code,
        ],
    )


def generate_code_for_paths(schema: OASchema, models: set[str]) -> tuple[str, str]:
    route_functions: list[str] = []
    service_methods: list[str] = []
    for path, endpoint in schema.paths.items():
        for method_name, method in endpoint.items():
            # noinspection PyTypeChecker
            route_function, service_method = generate_method_code(
                path, method_name, method, models
            )
            route_functions.append(route_function)
            service_methods.append(service_method)
    return "\n\n".join(route_functions), "\n\n".join(service_methods)


def generate_method_code(
    path: str,
    method_name: Literal["get", "post", "put", "delete"],
    method: OAMethod,
    models: set[str],
) -> tuple[str, str]:
    pos_params: list[str] = []
    kwargs_params: list[str] = []
    pos_service_params: list[str] = []
    args_service_params: list[str] = []
    kwargs_service_params: list[str] = []
    service_args: list[str] = []
    service_kwargs: list[str] = []
    for parameter in method.parameters:
        param_name = camel_to_snake(parameter.name)
        param_type = "Any"
        param_default: str | None = None
        if parameter.schema_:
            param_type = to_py_type(
                parameter.schema_,
                f"{method.operationId}.{parameter.name}",
                models,
            )
            default_value = parameter.schema_.get("default", ...)
            if default_value is not ...:
                param_default = repr(default_value)
        if param_default is None:
            pos_params.append(f"{parameter.name}: {param_type}")
            pos_service_params.append(f"{param_name}: {param_type}")
            service_args.append(f"{param_name}={parameter.name}")
        else:
            kwargs_params.append(f"{parameter.name}: {param_type} = {param_default}")
            args_service_params.append(f"{param_name}: {param_type}")
            service_kwargs.append(f"{param_name}={parameter.name}")

    if method.requestBody:
        request_type = "Any"
        json_content = method.requestBody.content.get("application/json")
        if json_content and json_content.schema_:
            request_type = to_py_type(
                json_content.schema_, f"{method.operationId}.requestBody", models
            )
        request_param_name = _camel_to_snake(request_type)
        if method.requestBody.required:
            request_pos_param = f"{request_param_name}: {request_type}"
            pos_params.append(request_pos_param)
            pos_service_params.append(request_pos_param)
        else:
            request_kw_param = f"{request_param_name}: Optional[{request_type}] = None"
            kwargs_params.append(request_kw_param)
            kwargs_service_params.append(request_kw_param)
        service_args.append(f"{request_param_name}={request_param_name}")

    extra_status_code = ""
    if method.responses.get("201"):
        extra_status_code = ", status_code=201"

    param_list = ", ".join(
        [
            *pos_params,
            *[f"{k}: {v}" for k, v in magic_param_list],
            "service: Service = fastapi.Depends(get_service)",
            *kwargs_params,
        ]
    )
    service_param_list = ", ".join(
        [
            "self",
            *pos_service_params,
            *args_service_params,
            "*args",
            *kwargs_service_params,
            "**kwargs",
        ]
    )
    param_service_list = ", ".join(
        [
            *service_args,
            *[f"{k}={k}" for k, _ in magic_param_list],
            *service_kwargs,
        ]
    )

    return_types_, error_types = parse_responses(method, models, skip_errors=True)

    return_types = list(v[0] for v in return_types_.values())
    if not return_types:
        return_types = ["None"]
    return_types = sorted(return_types)

    return_type_union = " | ".join(set(return_types))
    py_op_name = camel_to_snake(method.operationId)
    method_doc = (
        method.description
        or (method.summary and method.summary.capitalize())
        or "No description provided."
    )
    return (
        (
            f"# noinspection PyPep8Naming\n"
            f"@app.{method_name}({path!r}{extra_status_code})\n"
            f"async def {py_op_name}({param_list}):\n"
            f"{C_TAB}return await service."
            f"{py_op_name}({param_service_list})\n"
        ),
        (
            f"{C_TAB}@abstractmethod\n"
            f"{C_TAB}async def {py_op_name}({service_param_list})"
            f" -> {return_type_union}:\n"
            f'{C_TAB}{C_TAB}"""{method_doc}"""\n'
        ),
    )


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase or camelCase to snake_case."""
    # Insert underscore before uppercase letters (except at the beginning), then lowercase everything
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


if __name__ == "__main__":
    main()
