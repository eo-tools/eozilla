#!/usr/bin/env python3
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


def format_folder(cmd, path):
    print(f"Formatting: {path}")
    subprocess.run(cmd + [str(path)], check=True)


root = pathlib.Path(__file__).resolve().parent.parent

for ws_folder in [(root / ws) for ws in workspaces]:
    for src_folder in [(ws_folder / f) for f in ("src", "tests")]:
        format_folder(["isort"], src_folder)
        format_folder(["ruff", "format"], src_folder)
