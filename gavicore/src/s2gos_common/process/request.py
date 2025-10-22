#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import sys
from io import StringIO
from pathlib import Path
from typing import Annotated, Any

import click
import pydantic
from pydantic import Field

from s2gos_common.models import ProcessDescription, ProcessRequest
from s2gos_common.util.obj import flatten_obj, nest_dict

SUBSCRIBER_EVENTS = {
    "success": "successUri",
    "failed": "failedUri",
    "progress": "inProgressUri",
}


# noinspection PyShadowingBuiltins
class ExecutionRequest(ProcessRequest):
    """
    Process execution request.
    Extends [ProcessRequest][ProcessRequest]

    - to allow the process identifier being part of the request,
    - to allow creating nested object values for input names with dots.

    Args:
        process_id: Process identifier
        dotpath: Whether dots in input names should be used to create
            nested object values. Defaults to `False`.
        inputs: Optional process inputs given as key-value mapping.
            Values may be of any JSON-serializable type accepted by
            the given process.
        outputs: Optional process outputs given as key-value mapping.
            Values are of type [Output][s2gos_common.models.Output]
            supported by the given process.
        subscriber: Optional subscriber of type
            [Subscriber][s2gos_common.models.Subscriber] comprising callback
            URLs that are informed about process status changes
            while the processing takes place.
    """

    process_id: Annotated[str, Field(title="Process identifier", min_length=1)]
    dotpath: Annotated[
        bool, Field(title="Whether to encode nested input values using dots ('.').")
    ] = False

    def to_process_request(self) -> ProcessRequest:
        """
        Convert this execution request into a process request as used by the
        `execute-process` operation.
        """
        inputs = self.inputs
        if inputs and self.dotpath:
            inputs = nest_dict(inputs)
        return ProcessRequest(
            inputs=inputs,
            outputs=self.outputs,
            response=self.response,
            subscriber=self.subscriber,
        )

    @classmethod
    def create(
        cls,
        process_id: str | None = None,
        dotpath: bool = False,
        request_path: str | None = None,
        inputs: list[str] | None = None,
        subscribers: list[str] | None = None,
    ) -> "ExecutionRequest":
        request_dict, _ = _read_execution_request(request_path)
        if process_id:
            request_dict["process_id"] = process_id
        if dotpath:
            request_dict["dotpath"] = dotpath
        inputs_dict = _parse_inputs(inputs)
        if inputs_dict:
            request_dict["inputs"] = dict(request_dict.get("inputs") or {})
            request_dict["inputs"].update(inputs_dict)
        subscriber_dict = _parse_subscribers(subscribers)
        if subscriber_dict:
            request_dict["subscriber"] = dict(request_dict.get("subscriber") or {})
            request_dict["subscriber"].update(subscriber_dict)
        try:
            return ExecutionRequest(**request_dict)
        except pydantic.ValidationError as e:
            raise click.ClickException(f"Execution request is invalid: {e}")

    @classmethod
    def from_process_description(
        cls,
        process_description: ProcessDescription,
        dotpath: bool = False,
    ) -> "ExecutionRequest":
        """
        Create an execution request from the given process description.

        Args:
            process_description: The process description
            dotpath: Whether to allow for dot-separated input
                names for nested object values

        Returns:
            The execution requests populated with default values.
        """
        return _from_process_description(process_description, dotpath)


def _read_execution_request(
    request_path: Path | str | None = None,
) -> tuple[dict[str, Any], str]:
    if not request_path:
        return {}, ""

    if request_path == "-":
        request_path = "<stdin>"
        # content = "\n".join(line for line in sys.stdin).strip()
        content = sys.stdin.read().strip()
        file_format = "json" if content.startswith("{") else "yaml"
    else:
        path = Path(request_path)
        content = path.read_text()
        file_format = "json" if path.suffix in (".json", ".JSON") else "yaml"

    if file_format == "json":
        import json

        request_dict = json.loads(content)
    else:
        import yaml

        request_dict = yaml.safe_load(StringIO(content))

    if not isinstance(request_dict, dict):
        raise click.ClickException(
            f"Request must be an object, but was type {type(request_dict).__name__}"
        )

    return request_dict, str(request_path)


def _parse_inputs(inputs: list[str] | None) -> dict[str, Any]:
    return dict(_parse_inputs_kv(kv) for kv in (inputs or []))


def _parse_inputs_kv(kv: str) -> tuple[str, str]:
    parts = kv.split("=", maxsplit=1)
    key, value = parts if len(parts) == 2 else (parts[0], "true")
    return _parse_input_name(key), _parse_input_value(value)


def _parse_input_name(key: str) -> str:
    norm_key = key.strip().replace("-", "_")

    property_names = key.split(".")
    for property_name in property_names:
        if not property_name.isidentifier():
            raise click.ClickException(f"Invalid request NAME: {key!r}")

    return norm_key


def _parse_input_value(value: str) -> Any:
    import json

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_subscribers(subscribers: list[str] | None) -> dict[str, str]:
    return dict(_parse_subscriber_kv(kv) for kv in (subscribers or []))


def _parse_subscriber_kv(kv: str) -> tuple[str, str]:
    try:
        key, value = kv.split("=", maxsplit=1)
    except ValueError:
        raise click.ClickException(
            f"Invalid subscriber item: must have form `EVENT=URL`, but was {kv!r}"
        )
    return _parse_subscriber_event(key), _parse_subscriber_url(value)


def _parse_subscriber_event(key: str):
    norm_key = SUBSCRIBER_EVENTS.get(key)
    if norm_key is None:
        raise click.ClickException(
            "Invalid subscriber EVENT: must be one of "
            f"[{'|'.join(SUBSCRIBER_EVENTS.keys())}], but was {key!r}"
        )
    return norm_key


def _parse_subscriber_url(value: str):
    from urllib.parse import urlparse

    url = urlparse(value)
    if not all([url.scheme in ("http", "https"), url.netloc]):
        raise click.ClickException(f"Invalid subscriber URL: {value!r}")
    return value


# noinspection PyShadowingBuiltins
def _from_process_description(
    process_description: ProcessDescription, dotpath: bool
) -> ExecutionRequest:
    inputs = {
        k: _get_schema_default_value(
            v.schema_.model_dump(mode="json", exclude_unset=True) if v.schema_ else None
        )
        for k, v in (process_description.inputs or {}).items()
    }
    if dotpath:
        inputs = flatten_obj(inputs)
    return ExecutionRequest(
        process_id=process_description.id, dotpath=dotpath, inputs=inputs
    )


def _get_schema_default_value(schema: Any) -> Any:
    if schema and isinstance(schema, dict):
        if "default" in schema:
            return schema["default"]
        if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
            return schema["enum"][0]
        if "type" in schema and isinstance(schema["type"], str) and schema["type"]:
            type_ = schema["type"]
            if type_ == "object" and "properties" in schema:
                properties_ = schema["properties"]
                if properties_ and isinstance(properties_, dict):
                    return {
                        p_name: _get_schema_default_value(p_schema)
                        for p_name, p_schema in properties_.items()
                    }
            return _JSON_DATA_TYPE_DEFAULT_VALUES.get(type_)
    return None


_JSON_DATA_TYPE_DEFAULT_VALUES: dict[str, Any] = {
    "null": None,
    "boolean": False,
    "integer": 0,
    "number": 0,
    "string": "",
    "array": [],
    "object": {},
}
