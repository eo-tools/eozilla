#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import textwrap
from pathlib import Path
from typing import Literal

from tools.common import (
    C_TAB,
    D_TAB,
    OPEN_API_PATH,
    EOZILLA_PATH,
    camel_to_snake,
    parse_responses,
    to_py_type,
    write_file,
)
from tools.openapi import OAMethod, OASchema, load_openapi_schema

GENERATOR_NAME = str(Path(__file__).name)

SYNC_CLIENT_PATH = EOZILLA_PATH / "cuiman/src/cuiman/api/client.py"
ASYNC_CLIENT_PATH = EOZILLA_PATH / "cuiman/src/cuiman/api/async_client.py"


code_header = """

from typing import Any, Optional

from gavicore.models import {{ model_imports }}

from .config import ClientConfig
from .async_client_mixin import AsyncClientMixin
from .client_mixin import ClientMixin
from .ishell import has_ishell as _  # noqa F401
from .transport import {{ uc_async }}Transport, TransportArgs
from .transport.httpx import HttpxTransport


class {{ uc_async }}Client({{ uc_async }}ClientMixin):
    \"\"\"    
    The client API for the web service ({{ hr_async }} mode).

    Args:
      config: Optional client configuration object. If given,
        other configuration arguments are ignored.
      config_path: Optional path of the configuration file to be loaded
      config_kwargs: Configuration settings as keyword arguments.
      api_url: The service URL of the OGC API - Processes.
    \"\"\"

    def __init__(
        self,
        *,
        config: Optional[ClientConfig] = None,
        config_path: Optional[str] = None,
        api_url: Optional[str] = None,
        _debug: bool = False,
        _transport: Optional[{{ uc_async }}Transport] = None,
        **config_kwargs,
    ):
        self._config = ClientConfig.create(
            config=config,
            config_path=config_path,
            api_url=api_url,
            **config_kwargs,
        )
        if not self._config.api_url:
            raise ValueError("Required setting 'api_url' not configured")
        self._transport = (
            HttpxTransport(
                api_url=self._config.api_url,
                headers=self._config.auth_headers,
                debug=_debug,
            )
            if _transport is None
            else _transport
        )

    @property
    def config(self) -> ClientConfig:
        return self._config

    def _repr_json_(self):
        # noinspection PyProtectedMember
        return self.config._repr_json_()

{{ client_methods }}        
"""


def main():
    schema = load_openapi_schema(OPEN_API_PATH)

    models: set[str] = set()
    client_methods = generate_api_code(schema, models, is_async=False)
    model_list = ", ".join(sorted(models))

    sync_code = code_header
    sync_code = sync_code.replace("{{ model_imports }}", model_list)
    sync_code = sync_code.replace("{{ client_methods }}", client_methods)
    sync_code = sync_code.replace("{{ uc_async }}", "")
    sync_code = sync_code.replace("{{ hr_async }}", "synchronous")

    write_file(
        GENERATOR_NAME,
        SYNC_CLIENT_PATH,
        [sync_code],
    )

    models: set[str] = set()
    client_methods = generate_api_code(schema, models, is_async=True)
    model_list = ", ".join(sorted(models))

    async_code = code_header
    async_code = async_code.replace("{{ model_imports }}", model_list)
    async_code = async_code.replace("{{ client_methods }}", client_methods)
    async_code = async_code.replace("{{ uc_async }}", "Async")
    async_code = async_code.replace("{{ hr_async }}", "asynchronous")

    write_file(
        GENERATOR_NAME,
        ASYNC_CLIENT_PATH,
        [async_code],
    )


def generate_api_code(schema: OASchema, models: set[str], is_async: bool) -> str:
    functions: list[str] = []
    for path, endpoint in schema.paths.items():
        for method_name, method in endpoint.items():
            # noinspection PyTypeChecker
            function_code = generate_function_code(
                path, method_name, method, models, is_async=is_async
            )
            functions.append(function_code)
    functions.append(generate_close_method_code(is_async))
    return "\n\n".join(functions)


def generate_function_code(
    path: str,
    method_name: Literal["get", "post", "put", "delete"],
    method: OAMethod,
    models: set[str],
    is_async: bool,
) -> str:
    param_args: list[str] = ["self"]
    param_kwargs: list[str] = []
    path_param_mappings: list[str] = []
    query_param_mappings: list[str] = []
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
            param_args.append(f"{param_name}: {param_type}")
        else:
            param_kwargs.append(f"{param_name}: {param_type} = {param_default}")
        if parameter.in_ == "path":
            path_param_mappings.append(f"{parameter.name!r}: {param_name}")
        elif parameter.in_ == "query":
            query_param_mappings.append(f"{parameter.name!r}: {param_name}")
        else:
            print(
                f"⚠️ Error: parameter {parameter.name!r}"
                f" in {parameter.in_!r} not supported"
            )

    request_type: str | None = None
    if method.requestBody:
        request_type = "Any"
        json_content = method.requestBody.content.get("application/json")
        if json_content and json_content.schema_:
            request_type = to_py_type(
                json_content.schema_, f"{method.operationId}.requestBody", models
            )
        if method.requestBody.required:
            param_args.append(f"request: {request_type}")
        else:
            param_kwargs.append(f"request: Optional[{request_type}] = None")

    param_list = ", ".join([*param_args, *param_kwargs, "**kwargs: Any"])
    path_param_dict = "{" + ", ".join(path_param_mappings) + "}"
    query_param_dict = "{" + ", ".join(query_param_mappings) + "}"

    return_types, error_types = parse_responses(method, models)

    if not return_types:
        return_types = {"200": "None"}

    function_doc = generate_function_doc(method)
    return_type_union = " | ".join(set(v[0] for v in return_types.values()))
    return_type_dict = (
        "{" + ", ".join([f"{k!r}: {v[0]}" for k, v in return_types.items()]) + "}"
    )
    error_type_dict = (
        "{" + ", ".join([f"{k!r}: {v[0]}" for k, v in error_types.items()]) + "}"
    )

    transport_args = [
        f"path={path!r}",
        f"method={method_name!r}",
        f"path_params={path_param_dict}" if path_param_mappings else None,
        f"query_params={query_param_dict}" if query_param_mappings else None,
        "request=request" if request_type else None,
        f"return_types={return_type_dict}" if return_types else None,
        f"error_types={error_type_dict}" if error_types else None,
        "extra_kwargs=kwargs",
    ]
    transport_args_list = ", ".join(a for a in transport_args if a is not None)

    return (
        f"{C_TAB}{'async ' if is_async else ''}"
        f"def {camel_to_snake(method.operationId)}({param_list})"
        f" -> {return_type_union}:\n"
        f"{function_doc}"
        f"{C_TAB}{C_TAB}return "
        f"{'await ' if is_async else ''}"
        f"self._transport.{'async_' if is_async else ''}call("
        f"TransportArgs({transport_args_list})"
        f")\n"
    )


def generate_close_method_code(is_async: bool) -> str:
    if is_async:
        return (
            f"{C_TAB}async def close(self):\n"
            f'{C_TAB}{C_TAB}"""Close this client."""\n'
            f"{C_TAB}{C_TAB}if self._transport is not None:"
            f"{C_TAB}{C_TAB}{C_TAB}await self._transport.async_close()"
        )
    else:
        return (
            f"{C_TAB}def close(self):\n"
            f'{C_TAB}{C_TAB}"""Close this client."""\n'
            f"{C_TAB}{C_TAB}if self._transport is not None:"
            f"{C_TAB}{C_TAB}{C_TAB}self._transport.close()"
        )


def generate_function_doc(method: OAMethod) -> str:
    doc_lines = method.description.split("\n") if method.description else []

    if method.parameters:
        if doc_lines and doc_lines[-1] != "":
            doc_lines.append("")
        doc_lines.append("Args:")
        for parameter in method.parameters:
            param_name = camel_to_snake(parameter.name)
            if parameter.description:
                param_desc_lines = parameter.description.split("\n")
                doc_lines.append(f"{D_TAB}{param_name}: {param_desc_lines[0]}")
                doc_lines.extend(
                    [f"{2 * D_TAB}{line}" for line in param_desc_lines[1:]]
                )
            else:
                doc_lines.append(f"{D_TAB}{param_name}:")
        doc_lines.append(f"{D_TAB}kwargs: Optional keyword arguments that may be")
        doc_lines.append(f"{D_TAB}{D_TAB}used by the underlying transport.")

    if method.requestBody:
        json_content = method.requestBody.content.get("application/json")
        if json_content:
            if method.requestBody.description:
                param_desc_lines = method.requestBody.description.split("\n")
                doc_lines.append(f"{D_TAB}request: {param_desc_lines[0]}")
                doc_lines.extend(
                    [f"{D_TAB}{D_TAB}{line}" for line in param_desc_lines[1:]]
                )
            else:
                doc_lines.append("  request:")

    return_types, error_types = parse_responses(method, set())

    def append_return_types(
        resp_types: dict[str, tuple[str, list[str]]], lines: list[str]
    ):
        lines.append("")
        lines.append("Returns:")
        for resp_code, (resp_type, desc_lines) in resp_types.items():
            if desc_lines:
                lines.append(f"{D_TAB}{resp_type}: {desc_lines[0]}")
                for desc_line in desc_lines[1:]:
                    lines.append(f"{D_TAB}{D_TAB}{desc_line}")
            else:
                lines.append(f"{D_TAB}{resp_type}:")

    def append_error_types(
        resp_types: dict[str, tuple[str, list[str]]], lines: list[str]
    ):
        lines.append("")
        lines.append("Raises:")
        lines.append(f"{D_TAB}ClientError: If the call to the web service fails")
        lines.append(f"{D_TAB}{D_TAB}with a status code != `2xx`.")
        if resp_types:
            lines.append("")
            for resp_code, (resp_type, desc_lines) in resp_types.items():
                if desc_lines:
                    lines.append(f"{D_TAB}{D_TAB}- `{resp_code}`: {desc_lines[0]}")
                    for desc_line in desc_lines[1:]:
                        lines.append(f"{D_TAB}{D_TAB}  {desc_line}")
                else:
                    lines.append(f"{D_TAB}{D_TAB}- `{resp_code}`:")

    if return_types:
        append_return_types(return_types, doc_lines)

    append_error_types(error_types, doc_lines)

    wrapped_doc_lines = []
    for line in doc_lines:
        if line and not line.startswith("|"):
            for subline in textwrap.wrap(line, 72):
                # TODO: prefix `subline` 1..N with leading whitespaces from `line`
                wrapped_doc_lines.append(subline)
        else:
            wrapped_doc_lines.append(line)
    doc_lines = ['"""', *wrapped_doc_lines, '"""']
    doc_lines = [f"{2 * C_TAB}{line}" for line in doc_lines]
    return "\n".join(doc_lines) + "\n"


if __name__ == "__main__":
    main()
