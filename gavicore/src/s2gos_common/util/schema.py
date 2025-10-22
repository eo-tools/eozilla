#  Copyright (c) 2025 by ESA DTE-S2GOS team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import copy
import json
from typing import Any

import pydantic

from s2gos_common.models import Schema


def create_schema_instance(name: str, schema: dict[str, Any]) -> Schema:
    try:
        return Schema(**schema)
    except pydantic.ValidationError:
        print(80 * ">")
        print("name:", name)
        print("schema:", json.dumps(schema, indent=2))
        print(80 * "<")
        raise


def create_json_schema(
    model_class: type[pydantic.BaseModel],
) -> dict[str, Any]:
    model_class.model_rebuild()
    schema = model_class.model_json_schema()
    schema = inline_schema_refs(schema)
    return backport_schema_to_openapi_3_0(schema)


def inline_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    defs: dict[str, Any] | None = schema.get("$defs")
    if not defs:
        return schema
    schema = copy.copy(schema)
    schema.pop("$defs")
    return _inline_schema_refs(schema, {f"#/$defs/{k}": v for k, v in defs.items()})


def _inline_schema_refs(schema: dict[str, Any], defs: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in defs:
            ref_schema = _inline_schema_refs(defs[ref], defs)
            schema = copy.copy(schema)
            schema.pop("$ref")
            schema.update(copy.deepcopy(ref_schema))
            return schema
    schema = copy.copy(schema)
    for k in ("allOf", "anyOf", "oneOf"):
        if k in schema:
            if isinstance(schema[k], list):
                schema[k] = [_inline_schema_refs(s, defs) for s in schema[k]]
    for k in ("items", "prefixItems", "additionalProperties"):
        if k in schema:
            if isinstance(schema[k], list):
                schema[k] = [_inline_schema_refs(s, defs) for s in schema[k]]
            else:
                schema[k] = _inline_schema_refs(schema[k], defs)
    for k in ("properties",):
        if k in schema:
            if isinstance(schema[k], dict):
                schema[k] = {
                    k: _inline_schema_refs(s, defs) for k, s in schema[k].items()
                }
    return schema


def backport_schema_to_openapi_3_0(schema: dict[str, Any]) -> dict[str, Any]:
    if "type" in schema:
        type_ = schema["type"]
        if type_ == "null":
            schema.pop("type")
            schema["nullable"] = True
    if "prefixItems" in schema:
        prefix_items = schema.pop("prefixItems")
        if prefix_items:
            # Care, this is a naive implementation:
            schema["items"] = backport_schema_to_openapi_3_0(prefix_items[0])
    for schema_key in ("items", "additionalProperties"):
        if schema_key in schema:
            if isinstance(schema[schema_key], (list, tuple)):
                schema[schema_key] = list(
                    map(backport_schema_to_openapi_3_0, schema[schema_key])
                )
            elif isinstance(schema[schema_key], dict):
                schema[schema_key] = backport_schema_to_openapi_3_0(schema[schema_key])
    for dict_key in ("properties", "$defs"):
        if dict_key in schema and isinstance(schema[dict_key], dict):
            schema[dict_key] = {
                k: backport_schema_to_openapi_3_0(v)
                for k, v in schema[dict_key].items()
            }
    for x_of_key in ("allOf", "anyOf", "oneOf"):
        if x_of_key in schema:
            schema[x_of_key] = list(
                map(backport_schema_to_openapi_3_0, schema[x_of_key])
            )
            if len(schema[x_of_key]) == 2:
                x_of_copy = [s for s in schema[x_of_key] if s != {"nullable": True}]
                if len(x_of_copy) == 1:
                    schema.pop(x_of_key)
                    schema.update(x_of_copy[0])
                    schema["nullable"] = True
    return schema
