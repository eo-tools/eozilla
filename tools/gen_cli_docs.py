#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import subprocess
from typing import Final

from tools.common import EOZILLA_PATH

DOCS_PATH: Final = EOZILLA_PATH / "docs"
TOOL_CONFIG = [
    [
        "Cuiman CLI",
        EOZILLA_PATH / "cuiman" / "src" / "cuiman" / "cli" / "cli.py",
        DOCS_PATH / "cuiman" / "cli.md",
    ],
    [
        "Wraptile CLI",
        EOZILLA_PATH / "wraptile" / "src" / "wraptile" / "cli.py",
        DOCS_PATH / "wraptile" / "cli.md",
    ],
    [
        "Procodile-Example CLI",
        EOZILLA_PATH / "procodile-example" / "src" / "procodile_example" / "cli.py",
        DOCS_PATH / "procodile" / "cli.md",
    ],
    [
        "Appligator CLI",
        EOZILLA_PATH / "appligator" / "src" / "appligator" / "cli.py",
        DOCS_PATH / "appligator" / "cli.md",
    ],
]


def generate_cli_docs():
    for title, source_path, target_path in TOOL_CONFIG:
        subprocess.run(
            [
                "typer",
                str(source_path),
                "utils",
                "docs",
                "--output",
                str(target_path),
                "--title",
                title,
            ]
        )


if __name__ == "__main__":
    # noinspection PyTypeChecker
    generate_cli_docs()
