#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

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


def main(
    *,
    func_module: str,
    func_qualname: str,
    inputs: dict[str, Any],
    output_keys: list[str] | None = None,
):
    func = resolve_function(func_module, func_qualname)

    result = func(**inputs)

    if output_keys:
        if isinstance(result, tuple):
            output = dict(zip(output_keys, result, strict=False))
        else:
            output = {output_keys[0]: result}
    else:
        output = {"return_value": result}

    # using env variables to allow for easy testing.
    XCOM_DIR = os.environ.get("AIRFLOW_XCOM_DIR", "/airflow/xcom")
    XCOM_FILE = os.path.join(XCOM_DIR, "return.json")

    os.makedirs(XCOM_DIR, exist_ok=True)
    with open(XCOM_FILE, "w") as f:
        json.dump(output, f)


if __name__ == "__main__":  # pragma: no cover
    import sys

    payload = json.loads(sys.argv[1])
    main(**payload)
