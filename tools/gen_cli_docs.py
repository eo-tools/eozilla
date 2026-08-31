#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

from typing import Final

from tools.common import EOZILLA_PATH
from pathlib import Path

import typer
from typer.cli import get_docs_for_click
from typer.main import get_command

from gavicore.util.dynimp import import_value


DOCS_PATH: Final = EOZILLA_PATH / "docs"
TOOL_CONFIG = [
    [
        "Cuiman CLI",
        "cuiman.cli.cli:cli",
        DOCS_PATH / "cuiman" / "cli.md",
    ],
    [
        "Wraptile CLI",
        "wraptile.cli:cli",
        DOCS_PATH / "wraptile" / "cli.md",
    ],
    [
        "Procodile-Example CLI",
        "procodile_example.cli:cli",
        DOCS_PATH / "procodile" / "cli.md",
    ],
    [
        "Appligator CLI",
        "appligator.cli:cli",
        DOCS_PATH / "appligator" / "cli.md",
    ],
]


def generate_cli_docs():
    for title, app_ref, target_path in TOOL_CONFIG:
        print(f"Writing docs for {title} to {target_path}")

        app = import_value(app_ref, type=typer.Typer, name="app_ref")

        click_obj = get_command(app)
        ctx = typer.Context(click_obj)

        docs = get_docs_for_click(
            obj=click_obj,
            ctx=ctx,
            title=title,
        )

        Path(target_path).write_text(f"{docs.strip()}\n", encoding="utf-8")


if __name__ == "__main__":
    # noinspection PyTypeChecker
    generate_cli_docs()
