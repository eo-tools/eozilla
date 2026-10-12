#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import textwrap
from pathlib import Path
from typing import Literal

from tools.common import (
    C_TAB,
    D_TAB,
    EOZILLA_PATH,
    OPEN_API_PATH,
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

from gavicore.models.core import {{ model_imports }}

from .async_client_mixin import AsyncClientMixin
from .client_mixin import ClientMixin
from .client_app_mixin import ClientAppMixin
from .config import ClientConfig
from .defaults import (
    DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL,
    DEFAULT_OPEN_JOB_RESULT_TIMEOUT,
)
from .ishell import has_ishell as _  # noqa F401
from .jobs import JobMonitor, JobOptions, async_wait_for_job, wait_for_job
from .transport import {{ uc_async }}Transport, TransportArgs


class {{ uc_async }}Client(ClientAppMixin, {{ uc_async }}ClientMixin):
    \"\"\"    
    The client API for the web service ({{ hr_async }} mode).

    Args:
      config: Optional configuration object. Explicit keyword settings override
        its values.
      config_type: Optional application configuration class. It owns the
        settings schema, defaults, environment namespace, and profile path.
        When omitted, a supplied ``config`` object's concrete type is used.
      config_path: Optional path of the configuration file to be loaded
      config_kwargs (Any): Configuration overrides, including ``auth``. An auth model
        or a dictionary containing ``auth_type`` replaces previous auth settings,
        even when the type is unchanged. A dictionary without ``auth_type``
        merges into the selected auth configuration, including nested mappings.
        If credentials are still missing, a matching profile's keyring entry may
        supply them; explicitly supplied credentials take precedence.
      api_url: The service URL of the OGC API - Processes.
    \"\"\"

    def __init__(
        self,
        *,
        config: Optional[ClientConfig] = None,
        config_type: type[ClientConfig] | None = None,
        config_path: Optional[str] = None,
        api_url: Optional[str] = None,
        _debug: bool = False,
        _transport: Optional[{{ uc_async }}Transport] = None,
        **config_kwargs,
    ):
        self._config = ClientConfig.create(
            config=config,
            config_type=config_type,
            config_path=config_path,
            api_url=api_url,
            **config_kwargs,
        )
        if not self._config.api_url:
            raise ValueError("Required setting 'api_url' not configured")
        self._transport = _transport
        self._debug = _debug
        self._init_client_runtime()

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

    is_job_results = camel_to_snake(method.operationId) == "get_job_results"
    if is_job_results:
        param_kwargs.extend(
            [
                "wait: bool = True",
                "timeout: float = DEFAULT_OPEN_JOB_RESULT_TIMEOUT",
                "poll_interval: float = DEFAULT_OPEN_JOB_JOB_POLL_INTERVAL",
                "monitor: JobMonitor | None = None",
            ]
        )
    param_list = ", ".join(
        [
            *param_args,
            *(["*"] if is_job_results else []),
            *param_kwargs,
            "**kwargs: Any",
        ]
    )
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

    wait_code = ""
    if is_job_results:
        await_ = "await " if is_async else ""
        wait_code = (
            f"{2 * C_TAB}if wait:\n"
            f"{3 * C_TAB}{await_}{'async_' if is_async else ''}wait_for_job(\n"
            f"{4 * C_TAB}self, {await_}self.get_job(job_id, **kwargs),\n"
            f"{4 * C_TAB}JobOptions(timeout=timeout, poll_interval=poll_interval, monitor=monitor),\n"
            f"{4 * C_TAB}**kwargs,\n"
            f"{3 * C_TAB})\n"
        )

    return (
        f"{C_TAB}{'async ' if is_async else ''}"
        f"def {camel_to_snake(method.operationId)}({param_list})"
        f" -> {return_type_union}:\n"
        f"{function_doc}"
        f"{wait_code}"
        f"{C_TAB}{C_TAB}transport = self._get_transport()\n"
        f"{C_TAB}{C_TAB}return "
        f"{'await ' if is_async else ''}"
        f"transport.{'async_' if is_async else ''}call("
        f"TransportArgs({transport_args_list})"
        f")\n"
    )


def generate_function_doc(method: OAMethod) -> str:
    doc_lines = method.description.split("\n") if method.description else []
    is_job_results = camel_to_snake(method.operationId) == "get_job_results"
    if is_job_results:
        doc_lines.extend(
            [
                "",
                "Wait for successful completion by default, then retrieve JobResults.",
                "Pass wait=False to request immediately (the previous behavior).",
                "Retrieval neither opens outputs nor downloads linked data.",
            ]
        )

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
        if is_job_results:
            doc_lines.extend(
                [
                    f"{D_TAB}wait: Poll accepted or running jobs until completion.",
                    f"{D_TAB}timeout: Maximum wait in seconds; defaults to 1800 (30 minutes).",
                    f"{D_TAB}{D_TAB}On timeout the remote job keeps running. Ignored if wait=False.",
                    f"{D_TAB}poll_interval: Seconds between polls; defaults to 0.5.",
                    f"{D_TAB}{D_TAB}Ignored if wait=False.",
                    f"{D_TAB}monitor: Optional JobMonitor for status/progress updates and",
                    f"{D_TAB}{D_TAB}explicit cancellation. Ignored if wait=False.",
                ]
            )
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
        for _resp_code, (resp_type, desc_lines) in resp_types.items():
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
            for resp_code, (_resp_type, desc_lines) in resp_types.items():
                if desc_lines:
                    lines.append(f"{D_TAB}{D_TAB}- `{resp_code}`: {desc_lines[0]}")
                    for desc_line in desc_lines[1:]:
                        lines.append(f"{D_TAB}{D_TAB}  {desc_line}")
                else:
                    lines.append(f"{D_TAB}{D_TAB}- `{resp_code}`:")

    if return_types:
        append_return_types(return_types, doc_lines)

    append_error_types(error_types, doc_lines)
    if is_job_results:
        doc_lines.extend(
            [
                f"{D_TAB}JobResultStatusError: If the job fails or is dismissed while waiting.",
                f"{D_TAB}TimeoutError: If the job does not finish within the timeout.",
            ]
        )

    wrapped_doc_lines = []
    for line in doc_lines:
        if line and not line.startswith("|"):
            for subline in textwrap.wrap(
                line, 72, break_long_words=False, break_on_hyphens=False
            ):
                # TODO: prefix `subline` 1..N with leading whitespaces from `line`
                wrapped_doc_lines.append(subline)
        else:
            wrapped_doc_lines.append(line)
    doc_lines = ['"""', *wrapped_doc_lines, '"""']
    doc_lines = [f"{2 * C_TAB}{line}" for line in doc_lines]
    return "\n".join(doc_lines) + "\n"


if __name__ == "__main__":
    main()
