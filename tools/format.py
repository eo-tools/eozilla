#!/usr/bin/env python3

#  Copyright (c) 2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import pathlib
import subprocess

workspaces = [
    "appligator",
    "cuiman",
    "eozilla",
    "gavicore",
    "procodile",
    "procodile-example",
    "wraptile",
    "cuiman",
]


def format_folder(cmd_prefix: list[str], path: pathlib.Path):
    cmd = cmd_prefix + [str(path)]
    print(f"Formatting: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


root = pathlib.Path(__file__).resolve().parent.parent

for ws_folder in [(root / ws) for ws in workspaces]:
    for src_folder in [(ws_folder / f) for f in ("src", "tests")]:
        format_folder(["isort"], src_folder)
        format_folder(["ruff", "format"], src_folder)
