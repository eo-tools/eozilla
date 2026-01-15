# run_step.py
# (this is run inside the image that is used by the KPO in Airflow)

import importlib
import json
import os
from typing import Any

INPUT_PREFIX = "STEP_INPUT_"


def resolve_function(module_name: str, qualname: str):
    module = importlib.import_module(module_name)
    obj = module
    for attr in qualname.split("."):
        obj = getattr(obj, attr)
    return obj

def main(*,
    func_module: str,
    func_qualname: str,
    inputs: dict[str, Any],
    output_keys: list[str] | None = None,
         ):

    func = resolve_function(func_module, func_qualname)

    result = func(**inputs)

    if output_keys:
        if isinstance(result, tuple):
            output = dict(zip(output_keys, result))
        else:
            output = {output_keys[0]: result}
    else:
        output = {"return_value": result}

    os.makedirs("/airflow/xcom", exist_ok=True)
    with open("/airflow/xcom/return.json", "w") as f:
        json.dump(output, f)
