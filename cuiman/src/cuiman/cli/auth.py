#  Copyright (c) 2025 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.

import typer
from rich import print

from cuiman.api.auth import AuthType, login_and_get_token

from .config import ClientConfig


def save_config(config: ClientConfig):
    # TODO: write to .eozilla
    pass


def register_login(t: typer.Typer, auth_strategy: AuthType):
    # TODO: this is still experimental

    @t.command()
    def login(ctx: typer.Context):
        """
        Perform login using username+password and store the returned token.
        Reads and updates the config stored in the Typer context.
        """
        config: ClientConfig = ctx.obj["config"]

        if config.auth_type != "login":
            print("[yellow]Auth strategy is not 'login'. No login needed.[/yellow]")
            raise typer.Exit(1)

        try:
            login_and_get_token(config)
            save_config(config)
            print("[green]Login successful! Token stored.[/green]")
        except Exception as e:
            print(f"[red]Login failed: {e}[/red]")
            raise typer.Exit(1)
