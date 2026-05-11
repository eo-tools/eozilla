#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# run_step.py
# (this is run inside the image that is used by the KPO in Airflow)

import importlib
import json
import os
import typing
from typing import Any

from pydantic import BaseModel

# Prefix used to identify step input environment variables.
# Reserved for future use if inputs are passed via env vars instead of argv.
INPUT_PREFIX = "STEP_INPUT_"


class _XComEncoder(json.JSONEncoder):
    """Serialize types that json.dump can't handle natively.

    Airflow reads step outputs from a JSON file (XCom).  Standard json.dump
    fails on Pydantic models and other domain objects, so we serialise them
    here rather than requiring every step function to return plain dicts.
    """

    def default(self, obj):
        if hasattr(obj, "model_dump"):  # Pydantic models (e.g. PathRef)
            return obj.model_dump()
        return str(obj)


_SCALAR_TYPES = (int, float, bool)


def _pydantic_type(hint) -> type[BaseModel] | None:
    """Return the Pydantic model class for a hint, including Optional[Model]."""
    if isinstance(hint, type) and issubclass(hint, BaseModel):
        return hint
    args = typing.get_args(hint)
    if args:
        non_none = [a for a in args if a is not type(None)]
        if (
            len(non_none) == 1
            and isinstance(non_none[0], type)
            and issubclass(non_none[0], BaseModel)
        ):
            return non_none[0]
    return None


def coerce_inputs(func, inputs: dict[str, Any]) -> dict[str, Any]:
    """Cast inputs to the types declared in func's signature.

    Airflow renders all Jinja {{ params.* }} as strings, so numeric params
    arrive as str even when declared as float/int in the process function.
    Pydantic models (e.g. PathRef) arrive as dicts after XCom round-trip and
    are reconstructed from the dict by calling the model's constructor.

    Coercion is best-effort: if introspection fails for any reason (e.g. a
    forward reference that can't be resolved at runtime) the original inputs
    are returned unchanged so the step function can handle or report the error
    itself.
    """
    try:
        # include_extras=False strips Annotated[X, ...] → X so we get the
        # bare type (e.g. float) rather than Annotated[float, Field(...)].
        hints = typing.get_type_hints(func, include_extras=False)
    except Exception:
        return inputs

    coerced = {}
    for key, value in inputs.items():
        hint = hints.get(key)
        if value is None:
            coerced[key] = value
        elif hint in _SCALAR_TYPES and isinstance(value, str):
            coerced[key] = hint(value)
        elif (model_cls := _pydantic_type(hint)) and not isinstance(value, model_cls):
            coerced[key] = model_cls(value)
        else:
            coerced[key] = value
    return coerced


def resolve_function(module_name: str, qualname: str):
    """Import *module_name* and return the object at *qualname*.

    *qualname* may be a dotted path to a nested attribute, e.g.
    ``"MyClass.my_method"``, which is walked attribute-by-attribute after the
    module is imported.
    """
    module = importlib.import_module(module_name)
    obj = module
    for attr in qualname.split("."):
        obj = getattr(obj, attr)
    return obj


def main(
    *,
    func_module: str,
    func_qualname: str,
    inputs: dict[str, Any],
    output_keys: list[str] | None = None,
):
    """Entry point invoked by the Airflow KubernetesPodOperator (KPO).

    The KPO launches this script inside the task container, passing a single
    JSON-encoded argument via ``sys.argv[1]`` with the keys:

    - ``func_module``: dotted module path of the step function.
    - ``func_qualname``: qualified name of the function within that module.
    - ``inputs``: keyword arguments forwarded to the function.
    - ``output_keys``: names to assign to the function's return value(s).
      If the function returns a tuple each element is paired with the
      corresponding key; a scalar return is stored under the first key.
      Omit to use the default key ``"return_value"``.

    Outputs are written as JSON to the XCom file so Airflow can pass them to
    downstream tasks.  The XCom directory defaults to ``/airflow/xcom`` but
    can be overridden via the ``AIRFLOW_XCOM_DIR`` environment variable for
    local testing.
    """
    func = resolve_function(func_module, func_qualname)
    inputs = coerce_inputs(func, inputs)

    result = func(**inputs)

    if output_keys:
        if isinstance(result, tuple):
            output = dict(zip(output_keys, result, strict=False))
        else:
            output = {output_keys[0]: result}
    else:
        output = {"return_value": result}

    XCOM_DIR = os.environ.get("AIRFLOW_XCOM_DIR", "/airflow/xcom")
    XCOM_FILE = os.path.join(XCOM_DIR, "return.json")

    os.makedirs(XCOM_DIR, exist_ok=True)
    with open(XCOM_FILE, "w") as f:
        json.dump(output, f, cls=_XComEncoder)


if __name__ == "__main__":  # pragma: no cover
    import sys

    payload = json.loads(sys.argv[1])
    main(**payload)
