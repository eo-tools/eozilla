#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import typer

# See also cuiman/src/cuiman/cli/cli.py
PROCESS_ID_ARGUMENT = typer.Argument(
    help="Process identifier.",
)

# See also cuiman/src/cuiman/cli/cli.py
REQUEST_INPUT_OPTION = typer.Option(
    "--input",
    "-i",
    help="Process input value.",
    metavar="[NAME=VALUE]...",
)

# See also cuiman/src/cuiman/cli/cli.py
REQUEST_SUBSCRIBER_OPTION = typer.Option(
    "--subscriber",
    "-s",
    help="Process subscriber URL.",
    metavar="[NAME=URL]...",
)

DOT_PATH_OPTION = typer.Option(
    ...,
    "--dotpath",
    "-d",
    is_flag=True,
    help="Input names use dot-path notion to encode nested values, e.g., `-i scene.colors.bg=red`.",
)

# See also cuiman/src/cuiman/cli/cli.py
REQUEST_FILE_OPTION = typer.Option(
    ...,
    "--request",
    "-r",
    help="Execution request file. Use `-` to read from <stdin>.",
    metavar="PATH",
)
