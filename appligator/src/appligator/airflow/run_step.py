# run_step.py
# (this is run inside the image that is used by the KPO in Airflow)

import importlib
import json
import os

INPUT_PREFIX = "STEP_INPUT_"


def resolve_function(module_name, qualname):
    module = importlib.import_module(module_name)
    obj = module
    for attr in qualname.split("."):
        obj = getattr(obj, attr)
    return obj


def main():
    func = resolve_function(
        os.environ["STEP_FUNC_MODULE"],
        os.environ["STEP_FUNC_QUALNAME"],
    )

    inputs = {
        k[len(INPUT_PREFIX) :]: v
        for k, v in os.environ.items()
        if k.startswith(INPUT_PREFIX)
    }

    result = func(**inputs)

    raw_output_keys = os.environ.get("STEP_OUTPUT_KEYS", "")
    output_keys = [k for k in raw_output_keys.split(",") if k]

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
