#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import subprocess
from typing import Final

from tools.common import EOZILLA_PATH

DOCS_PATH: Final = EOZILLA_PATH / "docs"
CLI_APP_SOURCE: Final = EOZILLA_PATH / "cuiman" / "src" / "cuiman" / "cli" / "cli.py"
OUTPUT_FILE: Final = DOCS_PATH / "client-cli.md"


def generate_docs():
    subprocess.run(
        [
            "typer",
            str(CLI_APP_SOURCE),
            "utils",
            "docs",
            "--output",
            str(OUTPUT_FILE),
            "--title",
            "Client CLI Reference",
        ]
    )


if __name__ == "__main__":
    # noinspection PyTypeChecker
    generate_docs()
