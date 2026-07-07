#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

# run_step.py
# (this is run inside the image that is used by the KPO in Airflow)

import importlib
import json
import logging
import os
import typing
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from gavicore.util.dynimp import import_value

logger = logging.getLogger("appligator.airflow")

# Prefix used to identify step input environment variables.
# Reserved for future use if inputs are passed via env vars instead of argv.
INPUT_PREFIX = "STEP_INPUT_"


def coerce_inputs(func: Callable[..., Any], inputs: dict[str, Any]) -> dict[str, Any]:
    """Cast Airflow XCom inputs to the types declared in the signature of `func`.

    Airflow renders all Jinja {{ params.* }} as strings, so numeric params
    arrive as str even when declared as float/int in the process function.
    Pydantic models (e.g. PathRef) arrive as dicts after XCom round-trip.
    We use the function's type hints (with Annotated stripped) to coerce them.

    Coercion is best-effort: if introspection fails for any reason (e.g. a
    forward reference that can't be resolved at runtime) we fall back to
    JSON-parsing string values so that "5.0" → 5.0, "true" → True, etc.
    """
    try:
        # include_extras=False strips Annotated[X, ...] → X so we get the
        # bare type (e.g. float) rather than Annotated[float, Field(...)].
        hints = typing.get_type_hints(func, include_extras=False)
    except Exception:
        hints = {}  # fall through to json.loads fallback below

    coerced: dict[str, Any] = {}
    for key, value in inputs.items():
        if value is None:
            coerced[key] = value
            continue
        hint = hints.get(key)
        if hint in _SCALAR_TYPES and isinstance(value, str):
            coerced[key] = hint(value)
        elif (model_cls := _pydantic_type(hint)) and not isinstance(value, model_cls):
            if isinstance(value, str):
                # Airflow Jinja renders dict XCom/param values as Python repr
                # strings (single-quoted, None not null). Try JSON first, then
                # ast.literal_eval to recover the dict before model construction.
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    try:
                        import ast
                        value = ast.literal_eval(value)
                    except (ValueError, SyntaxError):  # pragma: no cover
                        pass
            try:
                coerced[key] = model_cls.model_validate(value)
            except ValidationError:
                # OGC job results are a mapping of output name -> value
                # (Link | QualifiedValue | InlineValue); a procodile Workflow
                # called directly returns that same shape for its single
                # output. The output name is arbitrary per OGC (procodile
                # only defaults it to "return_value" when none is declared),
                # so unwrap by shape -- a single-entry dict -- rather than
                # matching a specific key.
                if not isinstance(value, dict) or len(value) != 1:
                    raise
                (inner_value,) = value.values()
                coerced[key] = model_cls.model_validate(inner_value)
        elif isinstance(value, str):
            # Fallback: JSON-parse strings that look like non-string scalars.
            # "5.0" → 5.0, "true" → True, but "dummy" stays "dummy".
            try:
                parsed = json.loads(value)
                coerced[key] = parsed if not isinstance(parsed, str) else value
            except (json.JSONDecodeError, ValueError):
                coerced[key] = value
        else:
            coerced[key] = value
    return coerced


def resolve_function(module_name: str, qualname: str):
    """Import *module_name* and return the object at *qualname*.

    *qualname* may be a dotted path to a nested attribute, e.g.
    ``"MyClass.my_method"``, resolved via gavicore's
    ``import_value("module:qualname", ...)``.

    If the final segment of *qualname* is ``"function"`` and it can't be
    resolved directly but the parent object is a procodile Workflow (which
    stores its main callable in registry.main), the main function is
    extracted from the registry instead. This handles both old procodile
    builds (no .function property) and new ones transparently.
    """
    importlib.import_module(module_name)  # let ImportError propagate as-is
    try:
        obj = import_value(f"{module_name}:{qualname}", type=object, name="step target")
    except ValueError as e:
        attr = qualname.rsplit(".", 1)[-1]
        if attr != "function":
            raise AttributeError(str(e)) from e

        parent_qualname = qualname.rsplit(".", 1)[0] if "." in qualname else None
        try:
            parent = (
                import_value(
                    f"{module_name}:{parent_qualname}", type=object, name="step target"
                )
                if parent_qualname
                else importlib.import_module(module_name)
            )
        except ValueError as pe:
            raise AttributeError(str(pe)) from pe

        if not (hasattr(parent, "registry") and hasattr(parent.registry, "main")):
            raise AttributeError(str(e)) from e

        try:
            main_id = next(iter(parent.registry.main))
        except StopIteration:
            raise AttributeError(
                f"Workflow registry has no main step (attr={attr!r})"
            ) from None
        obj = parent.registry.main[main_id].function

    # If the resolved object is a procodile Step (has a .function attribute
    # holding the original callable), use the bare function so that calling it
    # returns the raw result rather than a procodile-wrapped output dict.
    if hasattr(obj, "function") and callable(obj.function):
        obj = obj.function

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
    logger.debug("RAW inputs: %s", inputs)
    inputs = coerce_inputs(func, inputs)
    logger.debug("COERCED inputs: %s", inputs)

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
    """Return the Pydantic model class from a hint, including Optional[Model]."""
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


if __name__ == "__main__":  # pragma: no cover
    import sys

    payload = json.loads(sys.argv[1])
    main(**payload)
